from typing import Dict, Any, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class VerificationResult(BaseModel):
    decision: str = Field(..., description="Trust decision: APPROVED, NEEDS_HUMAN_APPROVAL, or BLOCKED")
    risk_score: float = Field(..., description="Calculated composite risk score (0.0 to 1.0)")
    reason_codes: List[str] = Field(default_factory=list, description="Reason codes raised during evaluation")
    explanation: str = Field(..., description="Human-readable decision explanation")
    rules_evaluated: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed checks breakdown")
    proof_chip: Dict[str, Any] = Field(default_factory=dict, description="Verifiable proof metadata and raw telemetry")
    evaluated_at: str = Field(..., description="Evaluation timestamp in ISO 8601")

    @property
    def is_approved(self) -> bool:
        return self.decision == "APPROVED"

    @property
    def is_blocked(self) -> bool:
        return self.decision == "BLOCKED"

    @property
    def needs_human_approval(self) -> bool:
        return self.decision == "NEEDS_HUMAN_APPROVAL"

