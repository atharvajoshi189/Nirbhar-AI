from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.security.agent_keys import agent_key_manager, AGENT_ROLES
from app.db.supabase import get_supabase_admin_client

router = APIRouter(prefix="/agents", tags=["Agent Registry & Keys"])

class AgentRegistrationRequest(BaseModel):
    user_id: str

class VerifySignatureRequest(BaseModel):
    role: str
    payload: Dict[str, Any]
    signature: str

@router.get("/keys")
async def get_agent_public_keys():
    """
    Returns public keys for the 3 registered agents:
    - coordinator
    - research
    - service
    Private keys are never exposed and stay in server-side secure storage.
    """
    return {
        "status": "active",
        "algorithm": "Ed25519",
        "public_keys": agent_key_manager.get_public_keys()
    }

@router.post("/register")
async def register_agents_for_user(req: AgentRegistrationRequest):
    """
    Registers the 3 mandatory agents for a given user in Supabase public.agents:
    - coordinator
    - research
    - service
    """
    try:
        supabase = get_supabase_admin_client()
        public_keys = agent_key_manager.get_public_keys()
        registered = []

        for role in AGENT_ROLES:
            pub_key = public_keys.get(role)
            agent_data = {
                "user_id": req.user_id,
                "name": f"AgentTrust {role.capitalize()} Agent",
                "role": role,
                "public_key": pub_key,
                "is_active": True,
            }
            # Upsert into agents table
            res = (
                supabase.table("agents")
                .upsert(agent_data, on_conflict="user_id,role")
                .execute()
            )
            registered.append(res.data[0] if res.data else agent_data)

        return {
            "status": "registered",
            "agents": registered
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/verify-signature")
async def verify_agent_signature(req: VerifySignatureRequest):
    """
    Validates that a proposal payload was signed by the authoritative private key of the given agent.
    """
    public_keys = agent_key_manager.get_public_keys()
    pub_key = public_keys.get(req.role)
    if not pub_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{req.role}' has no registered public key."
        )

    is_valid = agent_key_manager.verify_signature(
        public_key_hex=pub_key,
        payload=req.payload,
        signature_hex=req.signature
    )
    return {
        "role": req.role,
        "valid": is_valid,
        "algorithm": "Ed25519"
    }
