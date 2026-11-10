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
        policy=task_policy
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
        "*, tasks(*), quotes(*), trust_decisions(*), user_approvals(*)"
    ).eq("id", tx_id).eq("user_id", user_id).execute()

    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transaction not found")

    tx = tx_res.data[0]
    task = tx.get("tasks") or {}
    quote = tx.get("quotes") or {}
    td_list = tx.get("trust_decisions") or []
    td = td_list[0] if td_list else {}

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
        "created_at": tx.get("created_at")
    }
