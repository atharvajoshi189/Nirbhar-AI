from enum import Enum
from typing import List, Dict, Any, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class TrustDecisionEnum(str, Enum):
    APPROVED = "APPROVED"
    NEEDS_HUMAN_APPROVAL = "NEEDS_HUMAN_APPROVAL"
    BLOCKED = "BLOCKED"

class TaskPolicyModel(BaseModel):
    auto_approve_threshold: Decimal = Decimal("50.00")
    single_tx_limit: Decimal = Decimal("200.00")
    allowed_domains: List[str] = Field(default_factory=list)
    blacklisted_domains: List[str] = Field(default_factory=list)
    strict_mode: bool = True

class ProposalEvaluationInput(BaseModel):
    task_id: str
    user_id: str
    agent_role: str
    amount: Decimal
    currency: str = "USD"
    vendor_name: str
    quote_url: str
    purpose: str
    quote_metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_signature: str
    task_budget_max: Decimal
    current_committed_spend: Decimal = Decimal("0.00")
    policy: TaskPolicyModel

class RuleResult(BaseModel):
    rule_name: str
    passed: bool
    decision_impact: TrustDecisionEnum
    reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TrustDecisionOutput(BaseModel):
    decision: TrustDecisionEnum
    risk_score: float  # 0.0 to 1.0
    rules_evaluated: List[RuleResult]
    decision_hash: str
    evaluated_at: str
    proof: Dict[str, Any]

