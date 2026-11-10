from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client
from app.security.auth import get_current_user
from app.services.audit import audit_service

router = APIRouter(prefix="/transactions", tags=["transactions"])

class ApprovalActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, description="Optional reviewer notes")

@router.get("", status_code=status.HTTP_200_OK)
async def list_transactions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Lists all transactions for the authenticated user.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select(
        "*, tasks(title, currency), trust_decisions(decision, risk_score, rules_evaluated, decision_hash), quotes(*)"
    ).eq("user_id", user_id).order("created_at", desc=True).execute()

    return tx_res.data or []

@router.get("/{tx_id}", status_code=status.HTTP_200_OK)
async def get_transaction(
    tx_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Gets full details for a single transaction.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select(
        "*, tasks(*), trust_decisions(*), quotes(*), user_approvals(*)"
    ).eq("id", tx_id).eq("user_id", user_id).execute()

    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return tx_res.data[0]

@router.post("/{tx_id}/approve", status_code=status.HTTP_200_OK)
async def approve_transaction(
    tx_id: str,
    payload: ApprovalActionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Human approval endpoint for transactions marked NEEDS_HUMAN_APPROVAL.
    Rule 4 (Security): Load authoritative record server-side. Zero client trust.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    # Load authoritative transaction
    tx_res = supabase.table("transactions").select("*").eq("id", tx_id).eq("user_id", user_id).execute()
    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx = tx_res.data[0]

    if tx["status"] != "NEEDS_HUMAN_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail=f"Transaction cannot be approved: current status is '{tx['status']}', expected 'NEEDS_HUMAN_APPROVAL'"
        )

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Insert user_approvals record
    approval_data = {
        "transaction_id": tx_id,
        "task_id": tx["task_id"],
        "user_id": user_id,
        "status": "APPROVED",
        "approved_at": now_iso,
        "notes": payload.notes or "Approved by user via Nirbhar AI dashboard"
    }
    supabase.table("user_approvals").insert(approval_data).execute()

    # 2. Update transaction status to APPROVED
    updated_tx = supabase.table("transactions").update({
        "status": "APPROVED",
        "updated_at": now_iso
    }).eq("id", tx_id).execute()

    # 3. Append to immutable audit chain
    audit_service.append_event(
        user_id=user_id,
        event_type="USER_APPROVAL_GRANTED",
        task_id=tx["task_id"],
        transaction_id=tx_id,
        payload={
            "transaction_id": tx_id,
            "amount": float(tx["amount"]),
            "currency": tx["currency"],
            "approved_at": now_iso,
            "notes": payload.notes
        }
    )

    return {
        "status": "APPROVED",
        "transaction_id": tx_id,
        "approved_at": now_iso,
        "message": "Human approval recorded. Transaction authorized for settlement."
    }

@router.post("/{tx_id}/reject", status_code=status.HTTP_200_OK)
async def reject_transaction(
    tx_id: str,
    payload: ApprovalActionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Human rejection endpoint.
    Sets transaction status to BLOCKED.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select("*").eq("id", tx_id).eq("user_id", user_id).execute()
    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx = tx_res.data[0]

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Insert user_approvals record as REJECTED
    approval_data = {
        "transaction_id": tx_id,
        "task_id": tx["task_id"],
        "user_id": user_id,
        "status": "REJECTED",
        "approved_at": now_iso,
        "notes": payload.notes or "Rejected by user via Nirbhar AI dashboard"
    }
    supabase.table("user_approvals").insert(approval_data).execute()

    # 2. Update transaction status to BLOCKED
    supabase.table("transactions").update({
        "status": "BLOCKED",
        "updated_at": now_iso
    }).eq("id", tx_id).execute()

    # 3. Append to immutable audit chain
    audit_service.append_event(
        user_id=user_id,
        event_type="USER_APPROVAL_REJECTED",
        task_id=tx["task_id"],
        transaction_id=tx_id,
        payload={
            "transaction_id": tx_id,
            "amount": float(tx["amount"]),
            "currency": tx["currency"],
            "rejected_at": now_iso,
            "notes": payload.notes
        }
    )

    return {
        "status": "BLOCKED",
        "transaction_id": tx_id,
        "rejected_at": now_iso,
        "message": "Transaction rejected by user. Payment blocked."
    }

