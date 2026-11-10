import hashlib
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import httpx

from app.config import settings
from app.db.supabase import get_supabase_admin_client
from app.security.auth import get_current_user
from app.security.agent_keys import agent_key_manager
from app.services.audit import audit_service

router = APIRouter(prefix="/transactions", tags=["transactions"])

class ApprovalActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, description="Optional reviewer notes")

class ProposalPayload(BaseModel):
    agent_id: str
    task_id: str
    provider: str
    service: str
    amount: float = Field(gt=0)
    currency: str = Field(default="USD")
    quote_id: str
    justification: str
    quote_details: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ProposeTransactionRequest(BaseModel):
    proposal: ProposalPayload
    signature: str

@router.get("", status_code=status.HTTP_200_OK)
async def list_transactions(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Lists all transactions for the authenticated user."""
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
    """Gets full details for a single transaction."""
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select(
        "*, tasks(*), trust_decisions(*), quotes(*), user_approvals(*)"
    ).eq("id", tx_id).eq("user_id", user_id).execute()

    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return tx_res.data[0]

@router.post("/propose", status_code=status.HTTP_201_CREATED)
async def propose_transaction(
    req: ProposeTransactionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Core Procurement & Trust Engine Gateway:
    1. Verifies the proposing agent's Ed25519 signature against stored public key.
    2. Verifies the quote's HMAC-SHA256 signature and 10-minute expiry with Vendor Gateway.
    3. Evaluates deterministic trust rules against task policies.
    4. Persists quote, transaction, trust_decision, and immutable audit record.
    Rule 4 (Security & Zero Client Trust): Fully authenticated and authoritative server-side.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()
    proposal = req.proposal
    signature = req.signature

    # 1. Fetch Agent Record and Verify Ed25519 Signature
    agent_res = supabase.table("agents").select("*").eq("id", proposal.agent_id).eq("user_id", user_id).execute()
    if not agent_res.data:
        raise HTTPException(status_code=403, detail="Proposing agent not registered or does not belong to user")
    agent = agent_res.data[0]

    if not agent.get("is_active"):
        raise HTTPException(status_code=403, detail="Proposing agent is currently deactivated")

    is_valid_sig = agent_key_manager.verify_signature(
        public_key_hex=agent["public_key"],
        payload=proposal.model_dump(),
        signature_hex=signature
    )
    if not is_valid_sig:
        raise HTTPException(
            status_code=401,
            detail="Agent Ed25519 signature verification failed. Proposal rejected (Rule 4: Zero Client Trust)."
        )

    # 2. Fetch Authoritative Task and Policy
    task_res = supabase.table("tasks").select("*, task_policies(*)").eq("id", proposal.task_id).eq("user_id", user_id).execute()
    if not task_res.data:
        raise HTTPException(status_code=404, detail="Associated task not found")
    task = task_res.data[0]

    policies = task.get("task_policies")
    if isinstance(policies, list) and len(policies) > 0:
        policy = policies[0]
    elif isinstance(policies, dict):
        policy = policies
    else:
        policy = {
            "auto_approve_threshold": 50.0,
            "single_tx_limit": float(task.get("budget_max", 50.0)),
            "allowed_domains": [],
            "blacklisted_domains": [],
            "strict_mode": True
        }

    # 3. Verify Quote Authenticity via Vendor Gateway (HMAC + Expiry)
    quote_details = proposal.quote_details or {}
    if quote_details.get("hmac_signature") and quote_details.get("expires_at"):
        try:
            async with httpx.AsyncClient(timeout=8.0) as http_client:
                vg_resp = await http_client.post(
                    f"{settings.VENDOR_GATEWAY_URL}/quote/verify",
                    json={
                        "quote_id": proposal.quote_id,
                        "merchant_id": quote_details.get("merchant_id", "merch_unknown"),
                        "payee_email": quote_details.get("payee_email", "payee@example.com"),
                        "amount": proposal.amount,
                        "currency": proposal.currency,
                        "expires_at": quote_details.get("expires_at"),
                        "hmac_signature": quote_details.get("hmac_signature")
                    }
                )
                if vg_resp.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Vendor Gateway rejected quote: {vg_resp.text}"
                    )
        except httpx.RequestError as e:
            # If vendor gateway communication glitched, fail closed
            raise HTTPException(status_code=502, detail=f"Vendor Gateway connection error: {e}")

    # 4. Deterministic Trust Engine Evaluation
    rules_evaluated: List[Dict[str, Any]] = []
    decision = "APPROVED"
    risk_score = 5.0

    # Rule A: Hard Budget Ceiling
    task_budget = float(task["budget_max"])
    # Calculate already committed transactions for this task
    existing_txs = supabase.table("transactions").select("amount, status").eq("task_id", proposal.task_id).execute()
    total_committed = sum(
        float(t["amount"]) for t in (existing_txs.data or []) if t["status"] in ("APPROVED", "COMPLETED", "EXECUTING", "NEEDS_HUMAN_APPROVAL")
    )
    if total_committed + proposal.amount > task_budget:
        decision = "BLOCKED"
        risk_score = 95.0
        rules_evaluated.append({
            "rule": "BUDGET_CEILING_CHECK",
            "passed": False,
            "reason": f"Transaction amount (${proposal.amount:.2f}) + existing committed (${total_committed:.2f}) exceeds task budget (${task_budget:.2f})"
        })
    else:
        rules_evaluated.append({
            "rule": "BUDGET_CEILING_CHECK",
            "passed": True,
            "message": f"Fits within task budget (${proposal.amount:.2f} <= ${task_budget - total_committed:.2f} remaining)"
        })

    # Rule B: Single Transaction Limit
    single_limit = float(policy.get("single_tx_limit") or task_budget)
    if decision != "BLOCKED":
        if proposal.amount > single_limit:
            decision = "BLOCKED"
            risk_score = 90.0
            rules_evaluated.append({
                "rule": "SINGLE_TX_LIMIT_CHECK",
                "passed": False,
                "reason": f"Amount (${proposal.amount:.2f}) exceeds single transaction limit (${single_limit:.2f})"
            })
        else:
            rules_evaluated.append({
                "rule": "SINGLE_TX_LIMIT_CHECK",
                "passed": True,
                "message": f"Amount fits single transaction ceiling (${proposal.amount:.2f} <= ${single_limit:.2f})"
            })

    # Rule C: Blacklisted Vendors
    blacklisted = policy.get("blacklisted_domains") or []
    if decision != "BLOCKED":
        if any(b.lower() in proposal.provider.lower() for b in blacklisted):
            decision = "BLOCKED"
            risk_score = 99.0
            rules_evaluated.append({
                "rule": "BLACKLIST_DOMAIN_CHECK",
                "passed": False,
                "reason": f"Provider '{proposal.provider}' is explicitly blacklisted"
            })
        else:
            rules_evaluated.append({
                "rule": "BLACKLIST_DOMAIN_CHECK",
                "passed": True,
                "message": "Provider is not on blacklist"
            })

    # Rule D: Auto-Approval Threshold
    auto_approve_threshold = float(policy.get("auto_approve_threshold") or 50.0)
    if decision != "BLOCKED":
        if proposal.amount > auto_approve_threshold:
            decision = "NEEDS_HUMAN_APPROVAL"
            risk_score = 30.0
            rules_evaluated.append({
                "rule": "AUTO_APPROVE_THRESHOLD_CHECK",
                "passed": False,
                "action": "Triggered human approval escalation",
                "reason": f"Amount (${proposal.amount:.2f}) exceeds auto-approval threshold (${auto_approve_threshold:.2f})"
            })
        else:
            rules_evaluated.append({
                "rule": "AUTO_APPROVE_THRESHOLD_CHECK",
                "passed": True,
                "message": f"Amount (${proposal.amount:.2f}) is within auto-approval threshold (${auto_approve_threshold:.2f})"
            })

    now_iso = datetime.now(timezone.utc).isoformat()

    # 5. Insert Record into quotes Table
    quote_insert = supabase.table("quotes").insert({
        "task_id": proposal.task_id,
        "user_id": user_id,
        "agent_id": proposal.agent_id,
        "vendor_name": proposal.provider,
        "quote_url": quote_details.get("quote_url", "http://127.0.0.1:8001/quote"),
        "amount": proposal.amount,
        "currency": proposal.currency,
        "quote_details": quote_details,
        "raw_metadata": {
            "quote_id": proposal.quote_id,
            "ed25519_signature": signature,
            "justification": proposal.justification
        }
    }).execute()
    saved_quote = quote_insert.data[0]
    quote_id = saved_quote["id"]

    # 6. Insert Record into transactions Table
    tx_insert = supabase.table("transactions").insert({
        "task_id": proposal.task_id,
        "user_id": user_id,
        "quote_id": quote_id,
        "amount": proposal.amount,
        "currency": proposal.currency,
        "status": decision,
        "created_at": now_iso
    }).execute()
    saved_tx = tx_insert.data[0]
    tx_id = saved_tx["id"]

    # 7. Insert Record into trust_decisions Table
    decision_payload = f"{tx_id}:{decision}:{proposal.amount:.2f}:{json.dumps(rules_evaluated)}"
    decision_hash = hashlib.sha256(decision_payload.encode()).hexdigest()

    decision_insert = supabase.table("trust_decisions").insert({
        "transaction_id": tx_id,
        "task_id": proposal.task_id,
        "user_id": user_id,
        "decision": decision,
        "rules_evaluated": rules_evaluated,
        "risk_score": risk_score,
        "decision_hash": decision_hash,
        "created_at": now_iso
    }).execute()
    saved_decision = decision_insert.data[0]

    # 8. Append to Immutable Audit Chain
    audit_service.append_event(
        user_id=user_id,
        event_type="TRANSACTION_EVALUATED_BY_TRUST_ENGINE",
        task_id=proposal.task_id,
        transaction_id=tx_id,
        payload={
            "transaction_id": tx_id,
            "quote_id": quote_id,
            "agent_id": proposal.agent_id,
            "provider": proposal.provider,
            "amount": proposal.amount,
            "currency": proposal.currency,
            "decision": decision,
            "risk_score": risk_score,
            "rules_evaluated": rules_evaluated,
            "ed25519_signature": signature,
            "decision_hash": decision_hash
        }
    )

    return {
        "transaction": saved_tx,
        "quote": saved_quote,
        "trust_decision": saved_decision,
        "proof": {
            "ed25519_verified": True,
            "agent_public_key": agent["public_key"],
            "decision_hash": decision_hash,
            "hmac_verified": bool(quote_details.get("hmac_signature"))
        }
    }

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
