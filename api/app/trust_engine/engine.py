import json
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any

from app.trust_engine.models import (
    ProposalEvaluationInput,
    RuleResult,
    TrustDecisionEnum,
    TrustDecisionOutput,
)
from app.trust_engine.rules import (
    evaluate_adversarial_patterns,
    evaluate_agent_signature,
    evaluate_budget_ceiling,
    evaluate_domain_policy,
    evaluate_single_tx_limit,
    evaluate_auto_approve_threshold,
)

class DeterministicTrustEngine:
    """
    Deterministic Trust and Authorization Engine.
    Evaluates agent proposals against mathematical invariants and security policies.
    Guarantees:
    - Zero simulation: strictly deterministic rule logic
    - Fail-closed: any runtime failure immediately yields BLOCKED
    - Tamper-evident: every decision generates a cryptographically hashed proof
    """

    def evaluate(self, input_data: ProposalEvaluationInput) -> TrustDecisionOutput:
        now_iso = datetime.now(timezone.utc).isoformat()
        rules_evaluated: List[RuleResult] = []
        overall_decision = TrustDecisionEnum.APPROVED
        risk_score = 0.0

        try:
            # 1. Adversarial & Prompt Injection Guardrail (Priority 1)
            inj_rule = evaluate_adversarial_patterns(input_data)
            rules_evaluated.append(inj_rule)
            if inj_rule.decision_impact == TrustDecisionEnum.BLOCKED:
                return self._finalize_decision(
                    decision=TrustDecisionEnum.BLOCKED,
                    risk_score=1.0,
                    rules=rules_evaluated,
                    input_data=input_data,
                    evaluated_at=now_iso,
                )

            # 2. Cryptographic Ed25519 Signature Verification (Priority 2)
            sig_rule = evaluate_agent_signature(input_data)
            rules_evaluated.append(sig_rule)
            if sig_rule.decision_impact == TrustDecisionEnum.BLOCKED:
                return self._finalize_decision(
                    decision=TrustDecisionEnum.BLOCKED,
                    risk_score=0.95,
                    rules=rules_evaluated,
                    input_data=input_data,
                    evaluated_at=now_iso,
                )

            # 3. Hard Task Budget Ceiling (Priority 3)
            budget_rule = evaluate_budget_ceiling(input_data)
            rules_evaluated.append(budget_rule)
            if budget_rule.decision_impact == TrustDecisionEnum.BLOCKED:
                return self._finalize_decision(
                    decision=TrustDecisionEnum.BLOCKED,
                    risk_score=0.90,
                    rules=rules_evaluated,
                    input_data=input_data,
                    evaluated_at=now_iso,
                )

            # 4. Domain Policy (Allowlist / Blacklist)
            domain_rule = evaluate_domain_policy(input_data)
            rules_evaluated.append(domain_rule)
            if domain_rule.decision_impact == TrustDecisionEnum.BLOCKED:
                return self._finalize_decision(
                    decision=TrustDecisionEnum.BLOCKED,
                    risk_score=0.85,
                    rules=rules_evaluated,
                    input_data=input_data,
                    evaluated_at=now_iso,
                )
            elif domain_rule.decision_impact == TrustDecisionEnum.NEEDS_HUMAN_APPROVAL:
                overall_decision = TrustDecisionEnum.NEEDS_HUMAN_APPROVAL
                risk_score += 0.40

            # 5. Single Transaction Policy Limit
            single_tx_rule = evaluate_single_tx_limit(input_data)
            rules_evaluated.append(single_tx_rule)
            if single_tx_rule.decision_impact == TrustDecisionEnum.NEEDS_HUMAN_APPROVAL:
                overall_decision = TrustDecisionEnum.NEEDS_HUMAN_APPROVAL
                risk_score += 0.30

            # 6. Auto-Approve Threshold
            auto_rule = evaluate_auto_approve_threshold(input_data)
            rules_evaluated.append(auto_rule)
            if auto_rule.decision_impact == TrustDecisionEnum.NEEDS_HUMAN_APPROVAL:
                overall_decision = TrustDecisionEnum.NEEDS_HUMAN_APPROVAL
                risk_score += 0.20

            # Compute relative spend risk: high fraction of remaining budget increases risk
            total_after_tx = input_data.current_committed_spend + input_data.amount
            budget_utilization = float(total_after_tx / input_data.task_budget_max)
            if budget_utilization > 0.8:
                risk_score += 0.15

            clamped_risk = min(max(round(risk_score, 2), 0.0), 1.0)

            return self._finalize_decision(
                decision=overall_decision,
                risk_score=clamped_risk,
                rules=rules_evaluated,
                input_data=input_data,
                evaluated_at=now_iso,
            )

        except Exception as e:
            # Rule 4 & 7: Fail Closed Default
            fail_closed_rule = RuleResult(
                rule_name="FAIL_CLOSED_PROTECTION",
                passed=False,
                decision_impact=TrustDecisionEnum.BLOCKED,
                reason=f"Engine runtime exception triggered fail-closed safety block: {str(e)}",
                metadata={"exception_class": e.__class__.__name__},
            )
            rules_evaluated.append(fail_closed_rule)
            return self._finalize_decision(
                decision=TrustDecisionEnum.BLOCKED,
                risk_score=1.0,
                rules=rules_evaluated,
                input_data=input_data,
                evaluated_at=now_iso,
            )

    def _finalize_decision(
        self,
        decision: TrustDecisionEnum,
        risk_score: float,
        rules: List[RuleResult],
        input_data: ProposalEvaluationInput,
        evaluated_at: str,
    ) -> TrustDecisionOutput:
        """Computes deterministic cryptographic SHA-256 hash over decision and rules."""
        raw_preimage_dict = {
            "task_id": input_data.task_id,
            "user_id": input_data.user_id,
            "amount": float(input_data.amount),
            "currency": input_data.currency,
            "vendor_name": input_data.vendor_name,
            "decision": decision.value,
            "risk_score": risk_score,
            "evaluated_at": evaluated_at,
            "rule_names": [r.rule_name for r in rules],
        }
        canonical_str = json.dumps(raw_preimage_dict, sort_keys=True, separators=(",", ":"))
        decision_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        return TrustDecisionOutput(
            decision=decision,
            risk_score=risk_score,
            rules_evaluated=rules,
            decision_hash=decision_hash,
            evaluated_at=evaluated_at,
            proof={
                "sha256": decision_hash,
                "engine": "Nirbhar AI-DeterministicEngine-v1",
                "rules_count": len(rules),
                "verified_at": evaluated_at,
                "input_summary": {
                    "task_id": input_data.task_id,
                    "amount": float(input_data.amount),
                    "vendor": input_data.vendor_name,
                },
            },
        )

trust_engine = DeterministicTrustEngine()
