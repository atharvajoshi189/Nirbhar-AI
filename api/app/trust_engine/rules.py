import re
from urllib.parse import urlparse
from decimal import Decimal
from typing import Tuple, List

from app.trust_engine.models import (
    ProposalEvaluationInput,
    RuleResult,
    TrustDecisionEnum,
)
from app.security.agent_keys import agent_key_manager

# Adversarial injection triggers
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"bypass\s+(approval|trust|budget|guardrail)", re.IGNORECASE),
    re.compile(r"admin\s+(override|access|command)", re.IGNORECASE),
    re.compile(r"disregard\s+(budget|limit|policy)", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"sudo\s+pay", re.IGNORECASE),
]

def extract_domain(url: str) -> str:
    """Extracts lowercase domain without port or credentials."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if "@" in netloc:
            netloc = netloc.split("@")[-1]
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        return netloc
    except Exception:
        return ""

def evaluate_budget_ceiling(input_data: ProposalEvaluationInput) -> RuleResult:
    """Rule 1: Hard task budget ceiling."""
    remaining = input_data.task_budget_max - input_data.current_committed_spend
    if input_data.amount > remaining:
        return RuleResult(
            rule_name="BUDGET_CEILING",
            passed=False,
            decision_impact=TrustDecisionEnum.BLOCKED,
            reason=f"Proposed amount (${input_data.amount}) exceeds remaining task budget (${remaining:.2f})",
            metadata={
                "task_budget_max": float(input_data.task_budget_max),
                "committed_spend": float(input_data.current_committed_spend),
                "remaining_budget": float(remaining),
                "requested_amount": float(input_data.amount),
            },
        )
    return RuleResult(
        rule_name="BUDGET_CEILING",
        passed=True,
        decision_impact=TrustDecisionEnum.APPROVED,
        reason="Proposed amount is within remaining task budget",
        metadata={"remaining_after_tx": float(remaining - input_data.amount)},
    )

def evaluate_single_tx_limit(input_data: ProposalEvaluationInput) -> RuleResult:
    """Rule 2: Single transaction limit."""
    if input_data.amount > input_data.policy.single_tx_limit:
        return RuleResult(
            rule_name="SINGLE_TX_LIMIT",
            passed=False,
            decision_impact=TrustDecisionEnum.NEEDS_HUMAN_APPROVAL,
            reason=f"Amount (${input_data.amount}) exceeds single transaction limit (${input_data.policy.single_tx_limit})",
            metadata={
                "amount": float(input_data.amount),
                "single_tx_limit": float(input_data.policy.single_tx_limit),
            },
        )
    return RuleResult(
        rule_name="SINGLE_TX_LIMIT",
        passed=True,
        decision_impact=TrustDecisionEnum.APPROVED,
        reason="Amount is within single transaction policy limit",
        metadata={"single_tx_limit": float(input_data.policy.single_tx_limit)},
    )

def evaluate_domain_policy(input_data: ProposalEvaluationInput) -> RuleResult:
    """Rule 3: Vendor domain allowlisting and blacklisting."""
    domain = extract_domain(input_data.quote_url)
    if not domain:
        return RuleResult(
            rule_name="DOMAIN_POLICY",
            passed=False,
            decision_impact=TrustDecisionEnum.BLOCKED,
            reason="Invalid, malformed, or unparseable quote URL",
            metadata={"raw_url": input_data.quote_url},
        )

    # 1. Blacklist check (Immediate Block)
    for bl in input_data.policy.blacklisted_domains:
        bl_clean = bl.strip().lower()
        if domain == bl_clean or domain.endswith(f".{bl_clean}"):
            return RuleResult(
                rule_name="DOMAIN_POLICY",
                passed=False,
                decision_impact=TrustDecisionEnum.BLOCKED,
                reason=f"Vendor domain '{domain}' is explicitly blacklisted by security policy",
                metadata={"matched_blacklist": bl_clean, "domain": domain},
            )

    # 2. Strict allowlist check
    if input_data.policy.strict_mode and input_data.policy.allowed_domains:
        matched = False
        for allowed in input_data.policy.allowed_domains:
            allowed_clean = allowed.strip().lower()
            if domain == allowed_clean or domain.endswith(f".{allowed_clean}"):
                matched = True
                break

        if not matched:
            return RuleResult(
                rule_name="DOMAIN_POLICY",
                passed=False,
                decision_impact=TrustDecisionEnum.NEEDS_HUMAN_APPROVAL,
                reason=f"Vendor domain '{domain}' is not in policy allowed domains list",
                metadata={
                    "domain": domain,
                    "allowed_domains": input_data.policy.allowed_domains,
                },
            )

    return RuleResult(
        rule_name="DOMAIN_POLICY",
        passed=True,
        decision_impact=TrustDecisionEnum.APPROVED,
        reason="Vendor domain satisfies allowlist/blacklist policies",
        metadata={"domain": domain},
    )

def evaluate_agent_signature(input_data: ProposalEvaluationInput) -> RuleResult:
    """Rule 4: Ed25519 signature authenticity check."""
    public_keys = agent_key_manager.get_public_keys()
    public_key = public_keys.get(input_data.agent_role)

    if not public_key:
        return RuleResult(
            rule_name="AGENT_SIGNATURE",
            passed=False,
            decision_impact=TrustDecisionEnum.BLOCKED,
            reason=f"Agent role '{input_data.agent_role}' does not have a registered public key",
            metadata={"role": input_data.agent_role},
        )

    payload_for_signing = {
        "task_id": input_data.task_id,
        "amount": float(input_data.amount),
        "currency": input_data.currency,
        "vendor_name": input_data.vendor_name,
        "quote_url": input_data.quote_url,
        "purpose": input_data.purpose,
    }

    is_valid = agent_key_manager.verify_signature(
        public_key_hex=public_key,
        payload=payload_for_signing,
        signature_hex=input_data.agent_signature,
    )

    if not is_valid:
        return RuleResult(
            rule_name="AGENT_SIGNATURE",
            passed=False,
            decision_impact=TrustDecisionEnum.BLOCKED,
            reason="Ed25519 cryptographic signature verification failed: proposal payload altered or unauthorized key",
            metadata={"role": input_data.agent_role},
        )

    return RuleResult(
        rule_name="AGENT_SIGNATURE",
        passed=True,
        decision_impact=TrustDecisionEnum.APPROVED,
        reason="Valid Ed25519 cryptographic signature from registered agent",
        metadata={"role": input_data.agent_role, "public_key": public_key[:16] + "..."},
    )

def evaluate_adversarial_patterns(input_data: ProposalEvaluationInput) -> RuleResult:
    """Rule 5: Prompt injection & adversarial keyword scan."""
    scan_text = f"{input_data.purpose} {input_data.vendor_name} {str(input_data.quote_metadata)}"

    for pattern in INJECTION_PATTERNS:
        match = pattern.search(scan_text)
        if match:
            return RuleResult(
                rule_name="ADVERSARIAL_INJECTION",
                passed=False,
                decision_impact=TrustDecisionEnum.BLOCKED,
                reason=f"Adversarial or prompt injection pattern detected: '{match.group(0)}'",
                metadata={"matched_pattern": match.group(0)},
            )

    return RuleResult(
        rule_name="ADVERSARIAL_INJECTION",
        passed=True,
        decision_impact=TrustDecisionEnum.APPROVED,
        reason="No prompt injection or adversarial patterns detected",
        metadata={"clean": True},
    )

def evaluate_auto_approve_threshold(input_data: ProposalEvaluationInput) -> RuleResult:
    """Rule 6: Auto-approval threshold check."""
    if input_data.amount <= input_data.policy.auto_approve_threshold:
        return RuleResult(
            rule_name="AUTO_APPROVE_THRESHOLD",
            passed=True,
            decision_impact=TrustDecisionEnum.APPROVED,
            reason=f"Amount (${input_data.amount}) is within auto-approval threshold (${input_data.policy.auto_approve_threshold})",
            metadata={
                "amount": float(input_data.amount),
                "threshold": float(input_data.policy.auto_approve_threshold),
            },
        )
    return RuleResult(
        rule_name="AUTO_APPROVE_THRESHOLD",
        passed=False,
        decision_impact=TrustDecisionEnum.NEEDS_HUMAN_APPROVAL,
        reason=f"Amount (${input_data.amount}) exceeds auto-approval threshold (${input_data.policy.auto_approve_threshold})",
        metadata={
            "amount": float(input_data.amount),
            "threshold": float(input_data.policy.auto_approve_threshold),
        },
    )

