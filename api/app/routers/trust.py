import os
import json
import time
import uuid
import hashlib
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Header, status
from pydantic import BaseModel, Field

from app.config import settings
from app.db.supabase import get_supabase_admin_client
from trust_engine.evaluator import evaluate_proposal
from trust_engine.models import (
    ProposalContext,
    TaskPolicyModel,
    TrustDecisionEnum,
    ReasonCode,
)

router = APIRouter(prefix="/trust", tags=["Trust Engine SDK Verification"])

class TrustVerifyRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Proposed spend amount")
    currency: str = Field("USD", description="Currency code (e.g. USD)")
    provider_name: str = Field(..., description="Target vendor or provider name")
    provider_url: str = Field(..., description="Provider API or website URL")
    proposal_category: str = Field("general", description="Service category")
    justification: str = Field(..., description="Agent's operational justification")
    task_id: Optional[str] = Field(None, description="Associated task ID")
    user_id: Optional[str] = Field(None, description="User ID owning the task")
    agent_id: Optional[str] = Field(None, description="Registered agent ID")
    signature: Optional[str] = Field(None, description="Ed25519 signature over proposal")
    signer_pubkey: Optional[str] = Field(None, description="Agent public key in hex")
    quote_id: Optional[str] = Field(None, description="Vendor quote ID")
    quote_amount: Optional[Decimal] = Field(None, description="HMAC signed quote amount")
    quote_currency: Optional[str] = Field("USD", description="Quote currency")
    quote_hmac_signature: Optional[str] = Field(None, description="Vendor HMAC quote signature")
    quote_expires_at: Optional[str] = Field(None, description="Quote expiration ISO timestamp")
    quote_merchant_id: Optional[str] = Field(None, description="Vendor merchant ID")
    quote_payee_email: Optional[str] = Field(None, description="PayPal merchant email")
    bypass_advisory_llm: bool = Field(False, description="Whether to bypass advisory Gemini scanner")

class RuleCheckResult(BaseModel):
    check_name: str
    passed: bool
    severity: str
    message: str

class ProofChipMetadata(BaseModel):
    request_id: str
    timestamp: str
    model_name: str
    api_name: str
    latency_ms: float
    sha256: str
    source_urls: List[str]
    raw: Dict[str, Any]

class TrustVerifyResponse(BaseModel):
    decision: str
    risk_score: float
    reason_codes: List[str]
    explanation: str
    rules_evaluated: List[Dict[str, Any]]
    proof_chip: ProofChipMetadata
    evaluated_at: str

@router.post("/verify", response_model=TrustVerifyResponse)
async def verify_proposal(
    req: TrustVerifyRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Evaluates an autonomous agent payment proposal through the live Trust Engine:
    - Pure deterministic 8-point security check
    - Cryptographic HMAC quote validation
    - Invariant spend limit and allowlist verification
    - Non-repudiation proof generation
    """
    start_time = time.perf_counter()

    # 1. Resolve user ID and task parameters
    user_id = req.user_id or "78036c01-215e-4df7-a627-7ff84aa44dbc"
    task_id = req.task_id or str(uuid.uuid4())
    task_budget = Decimal("50.00")
    task_title = "Agent Procurement Task"
    task_category = req.proposal_category or "general"

    # 2. Resolve Agent identity & Ed25519 public key
    agent_pubkey = req.signer_pubkey
    agent_is_active = True
    agent_id = req.agent_id or "agent_service_worker"

    # 3. Build Task Policy
    policy = TaskPolicyModel(
        auto_approve_threshold=Decimal("10.00"),
        single_tx_limit=Decimal("50.00"),
        allowed_domains=["cloudscale.io", "apexresearch.com", "localhost", "127.0.0.1"],
        blacklisted_domains=["dark-exploit-syndicate.ru", "malicious-actor.com"],
        strict_mode=True,
        policy_version="v2.0.0"
    )

    future_iso = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    quote_secret = settings.QUOTE_HMAC_SECRET

    context = ProposalContext(
        task_id=task_id,
        user_id=user_id,
        agent_id=agent_id,
        agent_public_key=agent_pubkey,
        agent_is_active=agent_is_active,
        amount=req.amount,
        currency=req.currency,
        provider_name=req.provider_name,
        provider_url=req.provider_url,
        proposal_category=req.proposal_category,
        task_title=task_title,
        task_category=task_category,
        task_budget_max=task_budget,
        current_committed_spend=Decimal("0.00"),
        justification=req.justification,
        quote_id=req.quote_id,
        quote_amount=req.quote_amount or req.amount,
        quote_currency=req.quote_currency or req.currency,
        quote_expires_at=req.quote_expires_at or future_iso,
        quote_hmac_signature=req.quote_hmac_signature,
        quote_hmac_secret=quote_secret,
        quote_merchant_id=req.quote_merchant_id or "merch_generic",
        quote_payee_email=req.quote_payee_email or "sb-vendor@business.example.com",
        policy=policy,
        bypass_advisory_llm=req.bypass_advisory_llm
    )

    # 4. Evaluate Pure Trust Engine
    decision_record = evaluate_proposal(context)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    req_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:12]}")
    now_iso = datetime.now(timezone.utc).isoformat()

    decision_val = decision_record.decision.value if hasattr(decision_record.decision, "value") else str(decision_record.decision)
    reason_codes = [rc.value if hasattr(rc, "value") else str(rc) for rc in decision_record.reason_codes]

    # Compute deterministic SHA-256 non-repudiation proof
    canonical_summary = f"{req_id}:{decision_val}:{req.amount}:{json.dumps(reason_codes)}"
    proof_hash = hashlib.sha256(canonical_summary.encode()).hexdigest()

    proof_chip = ProofChipMetadata(
        request_id=req_id,
        timestamp=now_iso,
        model_name="Deterministic Trust Engine v1.0",
        api_name="POST /trust/verify",
        latency_ms=latency_ms,
        sha256=proof_hash,
        source_urls=[req.provider_url],
        raw={
            "proposal": req.model_dump(mode="json"),
            "decision": decision_val,
            "risk_score": decision_record.risk_score,
            "reason_codes": reason_codes,
            "explanation": decision_record.explanation,
            "rules_evaluated": [c.model_dump() for c in decision_record.checks_list],
            "sha256": proof_hash,
            "latency_ms": latency_ms
        }
    )

    return TrustVerifyResponse(
        decision=decision_val,
        risk_score=decision_record.risk_score,
        reason_codes=reason_codes,
        explanation=decision_record.explanation,
        rules_evaluated=[c.model_dump() for c in decision_record.checks_list],
        proof_chip=proof_chip,
        evaluated_at=now_iso
    )
