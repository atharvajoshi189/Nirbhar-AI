from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class VerificationResult:
    """Deterministic decision and proof resulting from Nirbhar AI Trust Engine evaluation."""
    decision: str = ""
    risk_score: float = 0.0
    explanation: str = ""
    evaluated_at: str = ""
    reason_codes: List[str] = field(default_factory=list)
    rules_evaluated: List[Dict[str, Any]] = field(default_factory=list)
    proof_chip: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, **kwargs):
        self.decision = kwargs.get("decision", "")
        self.risk_score = float(kwargs.get("risk_score", 0.0))
        self.explanation = kwargs.get("explanation", "")
        self.evaluated_at = kwargs.get("evaluated_at", "")
        self.reason_codes = list(kwargs.get("reason_codes", []))
        self.rules_evaluated = list(kwargs.get("rules_evaluated", []))
        self.proof_chip = dict(kwargs.get("proof_chip", {}))

    @property
    def is_approved(self) -> bool:
        return self.decision == "APPROVED"

    @property
    def is_blocked(self) -> bool:
        return self.decision == "BLOCKED"

    @property
    def needs_human_approval(self) -> bool:
        return self.decision == "NEEDS_HUMAN_APPROVAL"

