from enum import Enum
from typing import List, Dict, Any, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class TrustDecisionEnum(str, Enum):
    APPROVED = "APPROVED"
    NEEDS_HUMAN_APPROVAL = "NEEDS_HUMAN_APPROVAL"
    BLOCKED = "BLOCKED"

class ReasonCode(str, Enum):
    AGENT_NOT_AUTHORIZED = "AGENT_NOT_AUTHORIZED"
    INVALID_TASK_REFERENCE = "INVALID_TASK_REFERENCE"
    TASK_MISMATCH = "TASK_MISMATCH"
    PROVIDER_NOT_ALLOWLISTED = "PROVIDER_NOT_ALLOWLISTED"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    QUOTE_EXPIRED = "QUOTE_EXPIRED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    USER_APPROVAL_REQUIRED = "USER_APPROVAL_REQUIRED"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
    SYSTEM_ERROR = "SYSTEM_ERROR"

class CheckType(str, Enum):
    AGENT_AUTHORIZATION = "agent_authorization"
    TASK_LINKAGE = "task_linkage"
    TASK_RELEVANCE = "task_relevance"
    PROVIDER_ALLOWLIST = "provider_allowlist"
    QUOTE_INTEGRITY = "quote_integrity"
    BUDGET_LIMIT = "budget_limit"
    APPROVAL_REQUIREMENT = "approval_requirement"
    REPLAY_PROTECTION = "replay_protection"

class CheckResult(BaseModel):
    check_name: str
    passed: bool
    severity: str = "HARD"  # "HARD" (blocks) or "SOFT" (needs review)
    impact: TrustDecisionEnum
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TaskPolicyModel(BaseModel):
    auto_approve_threshold: Decimal = Decimal("20.00")
    single_tx_limit: Decimal = Decimal("50.00")
    allowed_domains: List[str] = Field(default_factory=list)
    blacklisted_domains: List[str] = Field(default_factory=list)
    strict_mode: bool = False
    policy_version: str = "v1.0.0"

class ProposalContext(BaseModel):
    task_id: str
    user_id: str
    agent_id: str
    agent_role: str = "service_agent"
    agent_public_key: Optional[str] = None
    agent_is_active: bool = True
    agent_signature: Optional[str] = None
    amount: Decimal
    currency: str = "USD"
    provider_name: str
    provider_url: str = ""
    proposal_category: str = ""
    task_title: Optional[str] = ""
    task_category: Optional[str] = ""
    task_exists: bool = True
    task_owner_id: Optional[str] = None
    task_is_active: bool = True
    task_budget_max: Decimal
    current_committed_spend: Decimal = Decimal("0.00")
    justification: str = ""
    fetched_page_text: Optional[str] = ""
    advisory_relevance_score: Optional[float] = 1.0  # 0.0 to 1.0 from LLM
    quote_id: Optional[str] = None
    quote_amount: Optional[Decimal] = None
    quote_currency: Optional[str] = "USD"
    quote_expires_at: Optional[str] = None
    quote_hmac_signature: Optional[str] = None
    quote_hmac_secret: Optional[str] = None
    quote_merchant_id: Optional[str] = None
    quote_payee_email: Optional[str] = None
    human_approval_granted: bool = False
    idempotency_key: Optional[str] = None
    payload_hash: Optional[str] = None
    seen_idempotency_keys: List[str] = Field(default_factory=list)
    seen_payload_hashes: List[str] = Field(default_factory=list)
    canonical_payload_bytes: Optional[bytes] = None
    proposal_payload_dict: Optional[Dict[str, Any]] = None
    policy: TaskPolicyModel = Field(default_factory=TaskPolicyModel)
    bypass_advisory_llm: bool = False

class TrustDecision(BaseModel):
    decision: TrustDecisionEnum
    risk_score: float  # 0.0 to 100.0
    reason_codes: List[str] = Field(default_factory=list)
    explanation: str
    checks: Dict[str, CheckResult] = Field(default_factory=dict)
    checks_list: List[CheckResult] = Field(default_factory=list)
    decision_hash: str
    policy_version: str = "v1.0.0"
    evaluated_at: str
    proof: Dict[str, Any] = Field(default_factory=dict)
    eligible_for_human_review: bool = False

