from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.audit import audit_service, ChainVerificationResult
from app.db.supabase import get_supabase_admin_client

router = APIRouter(prefix="/audit", tags=["Audit Chain"])

class AuditEventInput(BaseModel):
    user_id: str
    task_id: Optional[str] = None
    transaction_id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]

@router.get("/verify", response_model=ChainVerificationResult)
async def verify_audit_chain(user_id: Optional[str] = Query(None, description="Optional filter by user_id")):
    """
    Recomputes the entire audit chain and verifies tamper-evidence.
    Rule 3: audit_events stores prev_hash and hash (SHA-256 over prev_hash + payload + AUDIT_SECRET).
    Detects any altered rows, dropped sequences, or modified values.
    """
    try:
        supabase = get_supabase_admin_client()
        query = supabase.table("audit_events").select("*").order("sequence_number", desc=False)
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.execute()
        events = response.data or []
        return audit_service.verify_chain(events)
    except ValueError as ve:
        # Credential missing
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit chain verification error: {str(e)}"
        )

@router.post("/events")
async def append_audit_event(event_in: AuditEventInput):
    """
    Authoritative backend endpoint to append an immutable event to the tamper-evident chain.
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get latest event for this user
        latest_res = (
            supabase.table("audit_events")
            .select("hash,sequence_number")
            .eq("user_id", event_in.user_id)
            .order("sequence_number", desc=True)
            .limit(1)
            .execute()
        )
        
        latest_rows = latest_res.data or []
        if latest_rows:
            prev_hash = latest_rows[0]["hash"]
            next_seq = latest_rows[0]["sequence_number"] + 1
        else:
            prev_hash = None
            next_seq = 1

        record = audit_service.build_event(
            user_id=event_in.user_id,
            event_type=event_in.event_type,
            payload=event_in.payload,
            sequence_number=next_seq,
            prev_hash=prev_hash,
            task_id=event_in.task_id,
            transaction_id=event_in.transaction_id,
        )

        insert_res = supabase.table("audit_events").insert(record.model_dump()).execute()
        return {
            "status": "appended",
            "sequence_number": record.sequence_number,
            "hash": record.hash,
            "prev_hash": record.prev_hash,
            "event": insert_res.data[0] if insert_res.data else record.model_dump()
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
