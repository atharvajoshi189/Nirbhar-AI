from typing import Dict, Any, Optional
from app.db.supabase import get_supabase_admin_client
from app.security.agent_keys import agent_key_manager

AGENT_ROLE_NAMES = {
    "coordinator": "Nirbhar Coordinator Agent",
    "research": "Nirbhar Research Agent",
    "service": "Nirbhar Service Procurement Agent"
}

def ensure_user_agent(user_id: str, role: str) -> str:
    """
    Ensures an agent record exists in Supabase public.agents for this user_id and role.
    Returns the agent UUID.
    """
    supabase = get_supabase_admin_client()
    res = supabase.table("agents").select("id").eq("user_id", user_id).eq("role", role).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]

    public_keys = agent_key_manager.get_public_keys()
    public_key = public_keys.get(role, "")

    insert_res = supabase.table("agents").insert({
        "user_id": user_id,
        "name": AGENT_ROLE_NAMES.get(role, f"Agent-{role}"),
        "role": role,
        "public_key": public_key,
        "is_active": True
    }).execute()

    return insert_res.data[0]["id"]
