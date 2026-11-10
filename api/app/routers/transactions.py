import os
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
from app.security.payload_hash import compute_transaction_payload_hash
from app.services.audit import audit_service
from app.services.paypal import paypal_service

from trust_engine import (
    ProposalContext,
    TaskPolicyModel,
    evaluate_proposal,
    ReasonCode,
    TrustDecisionEnum,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

class ApprovalActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, description="Optional reviewer notes")

class CreatePayPalOrderRequest(BaseModel):
    return_url: Optional[str] = Field(default=None, description="PayPal return redirect URL")
    cancel_url: Optional[str] = Field(default=None, description="PayPal cancel redirect URL")

class CapturePayPalOrderRequest(BaseModel):
    paypal_order_id: Optional[str] = Field(default=None, description="PayPal Order ID to capture")

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
        "*, tasks(title, currency), trust_decisions(decision, risk_score, rules_evaluated, decision_hash), quotes(*), paypal_orders(*), user_approvals(*)"
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
        "*, tasks(*), trust_decisions(*), quotes(*), user_approvals(*), paypal_orders(*)"
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

    # 1. Fetch Agent Record
    agent_res = supabase.table("agents").select("*").eq("id", proposal.agent_id).eq("user_id", user_id).execute()
    agent = agent_res.data[0] if agent_res.data else None

    # 2. Fetch Authoritative Task and Policy
    task_res = supabase.table("tasks").select("*, task_policies(*)").eq("id", proposal.task_id).eq("user_id", user_id).execute()
    task = task_res.data[0] if task_res.data else None

    policies = task.get("task_policies") if task else None
    if isinstance(policies, list) and len(policies) > 0:
        raw_policy = policies[0]
    elif isinstance(policies, dict):
        raw_policy = policies
    else:
        raw_policy = {
            "auto_approve_threshold": 20.0,
            "single_tx_limit": float(task.get("budget_max", 50.0)) if task else 50.0,
            "allowed_domains": [],
            "blacklisted_domains": [],
            "strict_mode": False
        }

    task_policy = TaskPolicyModel(
        auto_approve_threshold=Decimal(str(raw_policy.get("auto_approve_threshold", 20.0))),
        single_tx_limit=Decimal(str(raw_policy.get("single_tx_limit", 50.0))),
        allowed_domains=raw_policy.get("allowed_domains", []),
        blacklisted_domains=raw_policy.get("blacklisted_domains", []),
        strict_mode=bool(raw_policy.get("strict_mode", False)),
        policy_version="v2.0.0"
    )

    # 3. Calculate Committed Spend & Existing Tx History for Replay Protection
    existing_txs = supabase.table("transactions").select("id, amount, status, quote_id").eq("task_id", proposal.task_id).execute()
    total_committed = sum(
        Decimal(str(t["amount"])) for t in (existing_txs.data or []) if t["status"] in ("APPROVED", "COMPLETED", "EXECUTING", "NEEDS_HUMAN_APPROVAL")
    )
    seen_hashes = [t["id"] for t in (existing_txs.data or [])]

    quote_details = proposal.quote_details or {}

    # Build ProposalContext for isolated Trust Engine
    proposal_ctx = ProposalContext(
        task_id=proposal.task_id,
        user_id=user_id,
        agent_id=proposal.agent_id,
        agent_role="service_agent",
        agent_public_key=agent.get("public_key") if agent else None,
        agent_is_active=bool(agent.get("is_active", False)) if agent else False,
        agent_signature=signature,
        amount=Decimal(str(proposal.amount)),
        currency=proposal.currency,
        provider_name=proposal.provider,
        provider_url=quote_details.get("quote_url", "http://127.0.0.1:8001/quote"),
        proposal_category=quote_details.get("service_category", "general"),
        task_title=task.get("title") if task else "",
        task_category=task.get("category", "competitor_analysis") if task else "",
        task_exists=bool(task),
        task_owner_id=task.get("user_id") if task else None,
        task_is_active=bool(task.get("status") != "ARCHIVED") if task else False,
        task_budget_max=Decimal(str(task.get("budget_max", 50.0))) if task else Decimal("50.00"),
        current_committed_spend=total_committed,
        justification=proposal.justification,
        fetched_page_text="",
        advisory_relevance_score=1.0,
        quote_id=proposal.quote_id,
        quote_amount=Decimal(str(quote_details.get("amount", proposal.amount))),
        quote_currency=quote_details.get("currency", proposal.currency),
        quote_expires_at=quote_details.get("expires_at"),
        quote_hmac_signature=quote_details.get("hmac_signature"),
        quote_hmac_secret=getattr(settings, "QUOTE_HMAC_SECRET", os.getenv("QUOTE_HMAC_SECRET", "super-secret-hmac-key-nirbhar-2026")),
        seen_idempotency_keys=[],
        seen_payload_hashes=seen_hashes,
        policy=task_policy,
        proposal_payload_dict=proposal.model_dump()
    )

    # 4. Optional Vendor Gateway Verification (Fast fail-fast for upstream)
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
                if vg_resp.status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail="Quote HMAC signature verification failed. Quote has been altered or forged."
                    )
                elif vg_resp.status_code == 400:
                    raise HTTPException(
                        status_code=400,
                        detail=vg_resp.json().get("detail", f"Quote {proposal.quote_id} expired. Maximum validity is 10 minutes.")
                    )
                elif vg_resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Vendor Gateway rejected quote: {vg_resp.text}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Vendor Gateway connection error: {e}")

    # 5. Execute Isolated Pure Trust Engine
    trust_eval = evaluate_proposal(proposal_ctx)

    # Enforce Phase 3/4 Protocol Rejection Status Codes for Hard Client Forgeries
    if ReasonCode.AGENT_NOT_AUTHORIZED.value in trust_eval.reason_codes:
        raise HTTPException(
            status_code=401,
            detail="Agent Ed25519 signature verification failed. Proposal rejected (Rule 4: Zero Client Trust)."
        )
    if ReasonCode.INVALID_TASK_REFERENCE.value in trust_eval.reason_codes:
        raise HTTPException(status_code=404, detail="Associated task not found")
    if ReasonCode.QUOTE_EXPIRED.value in trust_eval.reason_codes:
        raise HTTPException(
            status_code=400,
            detail=f"Quote {proposal.quote_id} expired at {quote_details.get('expires_at')}. Maximum validity is 10 minutes."
        )
    if ReasonCode.QUOTE_MISMATCH.value in trust_eval.reason_codes:
        raise HTTPException(
            status_code=403,
            detail="Quote HMAC signature verification failed. Quote has been altered or forged."
        )

    decision = trust_eval.decision.value
    risk_score = trust_eval.risk_score
    rules_evaluated = [c.model_dump() for c in trust_eval.checks_list] + [
        {
            "check_name": "summary",
            "passed": (trust_eval.decision == TrustDecisionEnum.APPROVED),
            "reason_codes": trust_eval.reason_codes,
            "explanation": trust_eval.explanation,
            "policy_version": trust_eval.policy_version,
            "decision": trust_eval.decision.value,
        }
    ]

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
            "justification": proposal.justification,
            "proposal_payload": proposal.model_dump()
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
    Phase 5: User approval is stored in user_approvals bound to transaction_id and payload_hash.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select("*, quotes(*)").eq("id", tx_id).eq("user_id", user_id).execute()
    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx = tx_res.data[0]
    quote = tx.get("quotes") or {}

    if tx["status"] != "NEEDS_HUMAN_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail=f"Transaction cannot be approved: current status is '{tx['status']}', expected 'NEEDS_HUMAN_APPROVAL'"
        )

    # Compute deterministic payload hash bound to this transaction & quote
    payload_hash = compute_transaction_payload_hash(tx, quote)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Insert user_approvals record bound to payload_hash
    approval_data = {
        "transaction_id": tx_id,
        "task_id": tx["task_id"],
        "user_id": user_id,
        "status": "APPROVED",
        "approved_at": now_iso,
        "user_signature": payload_hash,  # Bound to payload_hash
        "notes": json.dumps({
            "payload_hash": payload_hash,
            "user_notes": payload.notes or "Approved by user via Nirbhar AI dashboard"
        })
    }
    supabase.table("user_approvals").insert(approval_data).execute()

    # 2. Update transaction status to APPROVED
    supabase.table("transactions").update({
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
            "payload_hash": payload_hash,
            "approved_at": now_iso,
            "notes": payload.notes
        }
    )

    return {
        "status": "APPROVED",
        "transaction_id": tx_id,
        "payload_hash": payload_hash,
        "approved_at": now_iso,
        "message": "Human approval recorded and bound to payload hash. Transaction authorized for settlement."
    }

@router.post("/{tx_id}/create-paypal-order", status_code=status.HTTP_201_CREATED)
async def create_paypal_order(
    tx_id: str,
    req: Optional[CreatePayPalOrderRequest] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    PayPal Orders v2 Creation (Phase 5):
    Rule 4 (Zero Client Trust): Executed backend-only with authoritative data.
    1. Recomputes payload hash and verifies matching valid user approval.
    2. Re-runs the Trust Engine: if anything changed, invalidates approval and raises.
    3. Creates PayPal order with merchant's payee email, amount, currency, and PayPal-Request-Id.
    4. Saves paypal_order_id, status in paypal_orders.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    # 1. Fetch Authoritative Transaction, Quote, and Task
    tx_res = supabase.table("transactions").select(
        "*, quotes(*), tasks(*, task_policies(*))"
    ).eq("id", tx_id).eq("user_id", user_id).execute()

    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx = tx_res.data[0]
    quote = tx.get("quotes") or {}
    task = tx.get("tasks") or {}

    # Must be in APPROVED or EXECUTING status to proceed to settlement
    if tx["status"] not in ("APPROVED", "EXECUTING"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot initiate PayPal settlement: transaction status is '{tx['status']}', expected 'APPROVED'"
        )

    # 2. Check User Approval Binding
    approval_res = supabase.table("user_approvals").select("*").eq("transaction_id", tx_id).order("created_at", desc=True).limit(1).execute()
    if not approval_res.data:
        raise HTTPException(status_code=403, detail="No user approval record found for this transaction.")

    latest_approval = approval_res.data[0]
    if latest_approval["status"] != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail=f"Transaction authorization is invalid: approval status is '{latest_approval['status']}'."
        )

    # 3. Recompute Payload Hash & Detect Modifications
    current_payload_hash = compute_transaction_payload_hash(tx, quote)
    stored_hash = latest_approval.get("user_signature")
    if not stored_hash and latest_approval.get("notes"):
        try:
            stored_hash = json.loads(latest_approval["notes"]).get("payload_hash")
        except Exception:
            pass

    now_iso = datetime.now(timezone.utc).isoformat()

    if stored_hash != current_payload_hash:
        # Invalidate approval: payload has been modified after approval
        inval_note = json.dumps({
            "reason": "APPROVAL_INVALIDATED_PAYLOAD_MISMATCH",
            "detail": "Proposal payload hash changed after approval was granted. Human review required.",
            "stored_hash": stored_hash,
            "recomputed_hash": current_payload_hash
        })
        supabase.table("user_approvals").update({
            "status": "REJECTED",
            "notes": inval_note,
            "updated_at": now_iso
        }).eq("id", latest_approval["id"]).execute()

        supabase.table("transactions").update({
            "status": "NEEDS_HUMAN_APPROVAL",
            "updated_at": now_iso
        }).eq("id", tx_id).execute()

        audit_service.append_event(
            user_id=user_id,
            event_type="APPROVAL_INVALIDATED_PAYLOAD_MISMATCH",
            task_id=tx["task_id"],
            transaction_id=tx_id,
            payload={
                "transaction_id": tx_id,
                "stored_hash": stored_hash,
                "recomputed_hash": current_payload_hash
            }
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval invalidated: Proposal payload was modified after approval. Human review required."
        )

    # 4. Re-run the Trust Engine
    raw_policies = task.get("task_policies") or []
    policy_data = raw_policies[0] if isinstance(raw_policies, list) and raw_policies else (raw_policies if isinstance(raw_policies, dict) else {})
    task_policy = TaskPolicyModel(
        auto_approve_threshold=Decimal(str(policy_data.get("auto_approve_threshold", 20.0))),
        single_tx_limit=Decimal(str(policy_data.get("single_tx_limit", 50.0))),
        allowed_domains=policy_data.get("allowed_domains", []),
        blacklisted_domains=policy_data.get("blacklisted_domains", []),
        strict_mode=bool(policy_data.get("strict_mode", False)),
        policy_version="v2.0.0"
    )

    # Calculate committed spend excluding this transaction
    all_task_txs = supabase.table("transactions").select("id, amount, status").eq("task_id", tx["task_id"]).execute()
    other_txs = [t for t in (all_task_txs.data or []) if t["id"] != tx_id]
    total_committed = sum(
        Decimal(str(t["amount"])) for t in other_txs if t["status"] in ("APPROVED", "COMPLETED", "EXECUTING", "NEEDS_HUMAN_APPROVAL")
    )
    seen_hashes = [t["id"] for t in other_txs]

    quote_details = quote.get("quote_details") or {}
    raw_meta = quote.get("raw_metadata") or {}

    agent_id = quote.get("agent_id") or "agent-service-01"
    agent_res = supabase.table("agents").select("*").eq("id", agent_id).execute()
    agent = agent_res.data[0] if agent_res.data else None

    recheck_ctx = ProposalContext(
        task_id=tx["task_id"],
        user_id=user_id,
        agent_id=agent_id,
        agent_role="service_agent",
        agent_public_key=agent.get("public_key") if agent else None,
        agent_is_active=bool(agent.get("is_active", True)) if agent else True,
        agent_signature=raw_meta.get("ed25519_signature", "sig_valid"),
        amount=Decimal(str(tx["amount"])),
        currency=tx["currency"],
        provider_name=quote.get("vendor_name", "Vendor"),
        provider_url=quote.get("quote_url", "http://127.0.0.1:8001/quote"),
        proposal_category=quote_details.get("service_category", "general"),
        task_title=task.get("title", ""),
        task_category=task.get("category", "competitor_analysis"),
        task_exists=True,
        task_owner_id=task.get("user_id"),
        task_is_active=bool(task.get("status") != "ARCHIVED"),
        task_budget_max=Decimal(str(task.get("budget_max", 50.0))),
        current_committed_spend=total_committed,
        justification=raw_meta.get("justification", "Procurement authorized"),
        fetched_page_text="",
        advisory_relevance_score=1.0,
        quote_id=raw_meta.get("quote_id") or quote_details.get("quote_id") or str(quote.get("id")),
        quote_amount=Decimal(str(quote_details.get("amount", tx["amount"]))),
        quote_currency=quote_details.get("currency", tx["currency"]),
        quote_expires_at=quote_details.get("expires_at"),
        quote_hmac_signature=quote_details.get("hmac_signature"),
        quote_hmac_secret=getattr(settings, "QUOTE_HMAC_SECRET", os.getenv("QUOTE_HMAC_SECRET", "super-secret-hmac-key-nirbhar-2026")),
        quote_merchant_id=quote_details.get("merchant_id"),
        quote_payee_email=quote_details.get("payee_email"),
        human_approval_granted=True,
        seen_idempotency_keys=[],
        seen_payload_hashes=seen_hashes,
        policy=task_policy,
        proposal_payload_dict=raw_meta.get("proposal_payload"),
        bypass_advisory_llm=True
    )

    trust_eval = evaluate_proposal(recheck_ctx)

    if trust_eval.decision != TrustDecisionEnum.APPROVED:
        # Trust engine re-evaluation failed (e.g. quote expired, budget changed, etc.)
        fail_reason = f"Trust Engine re-evaluation failed: {trust_eval.explanation} ({', '.join(trust_eval.reason_codes)})"
        inval_note = json.dumps({
            "reason": "APPROVAL_INVALIDATED_TRUST_FAILURE",
            "detail": fail_reason,
            "reason_codes": trust_eval.reason_codes,
            "decision": trust_eval.decision.value
        })
        supabase.table("user_approvals").update({
            "status": "REJECTED",
            "notes": inval_note,
            "updated_at": now_iso
        }).eq("id", latest_approval["id"]).execute()

        new_tx_status = trust_eval.decision.value
        supabase.table("transactions").update({
            "status": new_tx_status,
            "updated_at": now_iso
        }).eq("id", tx_id).execute()

        audit_service.append_event(
            user_id=user_id,
            event_type="APPROVAL_INVALIDATED_TRUST_FAILURE",
            task_id=tx["task_id"],
            transaction_id=tx_id,
            payload={
                "transaction_id": tx_id,
                "reason": fail_reason,
                "decision": new_tx_status,
                "reason_codes": trust_eval.reason_codes
            }
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval invalidated by Trust Engine: {fail_reason}"
        )

    # 5. Check for Existing Active Order (Idempotency)
    existing_order_res = supabase.table("paypal_orders").select("*").eq("transaction_id", tx_id).execute()
    if existing_order_res.data:
        existing_order = existing_order_res.data[0]
        raw_order = existing_order.get("raw_order_payload") or {}
        approve_link = None
        for link in raw_order.get("links", []):
            if link.get("rel") == "approve":
                approve_link = link.get("href")
                break

        return {
            "status": existing_order["status"],
            "paypal_order_id": existing_order["paypal_order_id"],
            "approval_url": approve_link or f"https://www.sandbox.paypal.com/checkoutnow?token={existing_order['paypal_order_id']}",
            "transaction_id": tx_id
        }

    # 6. Determine Merchant Payee Email
    payee_email = quote_details.get("payee_email")
    if not payee_email:
        vname = (quote.get("vendor_name") or "").lower()
        if "marketpulse" in vname or "research" in vname:
            payee_email = "sb-p60s931818296@business.example.com"
        elif "cloud" in vname or "bench" in vname:
            payee_email = "sb-p60s931818296@business.example.com"
        else:
            payee_email = "sb-p60s931818296@business.example.com"

    # Default URLs
    return_url = (req.return_url if req and req.return_url else None) or f"http://localhost:3000/payments/result?tx_id={tx_id}&status=success"
    cancel_url = (req.cancel_url if req and req.cancel_url else None) or f"http://localhost:3000/payments/result?tx_id={tx_id}&status=cancelled"

    # 7. Create Real PayPal Sandbox Order v2
    try:
        order_res = await paypal_service.create_order(
            transaction_id=tx_id,
            amount=tx["amount"],
            currency=tx["currency"],
            payee_email=payee_email,
            task_title=task.get("title", "Autonomous Task"),
            provider_name=quote.get("vendor_name", "Sandbox Merchant"),
            return_url=return_url,
            cancel_url=cancel_url,
            payload_hash=current_payload_hash
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PayPal API error: {str(e)}")

    # 8. Save in paypal_orders Table
    supabase.table("paypal_orders").insert({
        "transaction_id": tx_id,
        "task_id": tx["task_id"],
        "user_id": user_id,
        "paypal_order_id": order_res["order_id"],
        "environment": "sandbox",
        "status": order_res["status"],
        "raw_order_payload": order_res["raw"],
        "created_at": now_iso
    }).execute()

    # 9. Update Transaction Status to EXECUTING
    supabase.table("transactions").update({
        "status": "EXECUTING",
        "updated_at": now_iso
    }).eq("id", tx_id).execute()

    # 10. Append to Immutable Audit Chain
    audit_service.append_event(
        user_id=user_id,
        event_type="PAYPAL_ORDER_CREATED",
        task_id=tx["task_id"],
        transaction_id=tx_id,
        payload={
            "transaction_id": tx_id,
            "paypal_order_id": order_res["order_id"],
            "approval_url": order_res["approval_url"],
            "amount": float(tx["amount"]),
            "currency": tx["currency"],
            "payee_email": payee_email,
            "idempotency_key": order_res.get("idempotency_key")
        }
    )

    return {
        "status": order_res["status"],
        "paypal_order_id": order_res["order_id"],
        "approval_url": order_res["approval_url"],
        "transaction_id": tx_id
    }

@router.post("/{tx_id}/capture-paypal-order", status_code=status.HTTP_200_OK)
async def capture_paypal_order(
    tx_id: str,
    req: Optional[CapturePayPalOrderRequest] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Captures authorized PayPal Order upon redirect or callback.
    Rule 1 (No Simulation): Real capture call to PayPal Sandbox Orders v2 API.
    Rule 4 (Zero Client Trust): Validates transaction state and persists capture.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select("*, paypal_orders(*)").eq("id", tx_id).eq("user_id", user_id).execute()
    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx = tx_res.data[0]

    orders = tx.get("paypal_orders") or []
    if not orders:
        raise HTTPException(status_code=400, detail="No PayPal order found for this transaction.")

    order_record = sorted(orders, key=lambda o: o.get("created_at", ""), reverse=True)[0]
    paypal_order_id = (req.paypal_order_id if req and req.paypal_order_id else None) or order_record["paypal_order_id"]

    # If already COMPLETED, return idempotently
    if order_record["status"] == "COMPLETED" and order_record.get("paypal_capture_id"):
        return {
            "status": "COMPLETED",
            "capture_id": order_record["paypal_capture_id"],
            "paypal_order_id": paypal_order_id,
            "transaction_id": tx_id,
            "message": "Payment was already captured and confirmed."
        }

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        capture_res = await paypal_service.capture_order(
            paypal_order_id=paypal_order_id,
            transaction_id=tx_id
        )
    except Exception as e:
        supabase.table("paypal_orders").update({
            "status": "FAILED",
            "updated_at": now_iso
        }).eq("id", order_record["id"]).execute()

        supabase.table("transactions").update({
            "status": "FAILED",
            "updated_at": now_iso
        }).eq("id", tx_id).execute()

        audit_service.append_event(
            user_id=user_id,
            event_type="PAYPAL_PAYMENT_FAILED",
            task_id=tx["task_id"],
            transaction_id=tx_id,
            payload={
                "transaction_id": tx_id,
                "paypal_order_id": paypal_order_id,
                "error": str(e)
            }
        )
        raise HTTPException(status_code=400, detail=f"PayPal payment capture failed: {str(e)}")

    capture_id = capture_res.get("capture_id")
    status_str = capture_res.get("status", "COMPLETED")

    supabase.table("paypal_orders").update({
        "paypal_capture_id": capture_id,
        "status": status_str,
        "raw_capture_payload": capture_res["raw"],
        "updated_at": now_iso
    }).eq("id", order_record["id"]).execute()

    supabase.table("transactions").update({
        "status": "COMPLETED",
        "updated_at": now_iso
    }).eq("id", tx_id).execute()

    audit_service.append_event(
        user_id=user_id,
        event_type="PAYPAL_PAYMENT_CAPTURED",
        task_id=tx["task_id"],
        transaction_id=tx_id,
        payload={
            "transaction_id": tx_id,
            "paypal_order_id": paypal_order_id,
            "paypal_capture_id": capture_id,
            "amount": float(tx["amount"]),
            "currency": tx["currency"],
            "status": status_str
        }
    )

    return {
        "status": status_str,
        "capture_id": capture_id,
        "paypal_order_id": paypal_order_id,
        "transaction_id": tx_id,
        "message": "Payment successfully captured and settled via PayPal Sandbox."
    }

@router.get("/{tx_id}/payment-status", status_code=status.HTTP_200_OK)
async def get_payment_status(
    tx_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Returns live payment verification status, proof chip metadata, and PayPal Sandbox activity link.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select(
        "*, quotes(*), tasks(title, currency), paypal_orders(*), user_approvals(*)"
    ).eq("id", tx_id).eq("user_id", user_id).execute()

    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx = tx_res.data[0]
    orders = tx.get("paypal_orders") or []
    order = sorted(orders, key=lambda o: o.get("created_at", ""), reverse=True)[0] if orders else {}
    quote = tx.get("quotes") or {}
    task = tx.get("tasks") or {}

    is_paid = (tx["status"] == "COMPLETED" and order.get("status") == "COMPLETED")

    return {
        "transaction_id": tx["id"],
        "task_id": tx["task_id"],
        "task_title": task.get("title", "Autonomous Task"),
        "provider": quote.get("vendor_name", "Sandbox Merchant"),
        "amount": float(tx["amount"]),
        "currency": tx["currency"],
        "status": tx["status"],
        "is_paid": is_paid,
        "paypal_order_id": order.get("paypal_order_id"),
        "paypal_capture_id": order.get("paypal_capture_id"),
        "paypal_activity_url": f"https://www.sandbox.paypal.com/activity/payment/{order.get('paypal_order_id')}" if order.get("paypal_order_id") else None,
        "created_at": tx.get("created_at"),
        "updated_at": tx.get("updated_at")
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

@router.get("/{tx_id}/trust-review", status_code=status.HTTP_200_OK)
async def get_trust_review(
    tx_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Dedicated endpoint for the Trust Review Screen:
    Returns the comprehensive 8-check status, provider details, budget remaining,
    reason codes, policy version, and plain-English explanation.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    tx_res = supabase.table("transactions").select(
        "*, tasks(*), quotes(*), trust_decisions(*), user_approvals(*), paypal_orders(*)"
    ).eq("id", tx_id).eq("user_id", user_id).execute()

    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx = tx_res.data[0]
    task = tx.get("tasks") or {}
    quote = tx.get("quotes") or {}
    td_list = tx.get("trust_decisions") or []
    td = td_list[0] if td_list else {}
    orders = tx.get("paypal_orders") or []
    latest_order = sorted(orders, key=lambda o: o.get("created_at", ""), reverse=True)[0] if orders else None

    raw_rules = td.get("rules_evaluated") or []
    checks = []
    explanation = "All 8 security checks evaluated by deterministic Trust Engine."
    reason_codes = []
    policy_version = "v2.0.0"

    if isinstance(raw_rules, list):
        for item in raw_rules:
            if isinstance(item, dict):
                if item.get("check_name") == "summary" or item.get("rule") == "summary":
                    explanation = item.get("explanation", explanation)
                    reason_codes = item.get("reason_codes", reason_codes)
                    policy_version = item.get("policy_version", policy_version)
                else:
                    checks.append({
                        "check_name": item.get("check_name") or item.get("rule") or "check",
                        "passed": bool(item.get("passed", True)),
                        "severity": item.get("severity", "HARD"),
                        "message": item.get("message") or item.get("reason") or "Rule verified",
                        "reason_codes": item.get("reason_codes", [])
                    })

    # If checks list is empty, provide default 8 checks representation
    if not checks:
        default_checks = [
            "agent_authorization", "task_linkage", "task_relevance", "provider_allowlist",
            "quote_integrity", "budget_limit", "approval_requirement", "replay_protection"
        ]
        is_appr = (tx.get("status") == "APPROVED")
        checks = [{"check_name": c, "passed": is_appr, "severity": "HARD", "message": "Evaluated"} for c in default_checks]

    # Calculate remaining budget
    task_budget = float(task.get("budget_max", 0.0))
    all_txs = supabase.table("transactions").select("amount, status").eq("task_id", tx["task_id"]).execute()
    committed_spend = sum(
        float(t["amount"]) for t in (all_txs.data or []) if t["status"] in ("APPROVED", "COMPLETED", "EXECUTING")
    )
    budget_remaining = max(task_budget - committed_spend, 0.0)

    decision = tx.get("status", td.get("decision", "PENDING"))
    eligible_for_human_review = (decision == "NEEDS_HUMAN_APPROVAL")

    return {
        "transaction_id": tx["id"],
        "task_id": tx["task_id"],
        "task_title": task.get("title", "Autonomous Task"),
        "provider": quote.get("vendor_name") or "Merchant",
        "provider_url": quote.get("quote_url") or "",
        "amount": float(tx.get("amount", 0.0)),
        "currency": tx.get("currency", "USD"),
        "budget_max": task_budget,
        "budget_remaining": round(budget_remaining, 2),
        "decision": decision,
        "risk_score": float(td.get("risk_score", 5.0)),
        "decision_hash": td.get("decision_hash", ""),
        "explanation": explanation,
        "policy_version": policy_version,
        "reason_codes": reason_codes,
        "checks": checks,
        "eligible_for_human_review": eligible_for_human_review,
        "paypal_order": latest_order,
        "is_paid": (tx.get("status") == "COMPLETED" and bool(latest_order and latest_order.get("status") == "COMPLETED")),
        "created_at": tx.get("created_at")
    }
