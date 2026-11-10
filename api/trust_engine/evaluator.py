import json
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional

from .models import (
    ProposalContext,
    TrustDecision,
    TrustDecisionEnum,
    ReasonCode,
    CheckResult,
    CheckType,
)
from .checks import (
    check_agent_authorization,
    check_task_linkage,
    check_task_relevance,
    check_provider_allowlist,
    check_quote_integrity,
    check_budget_limit,
    check_approval_requirement,
    check_replay_protection,
    extract_domain,
)
from .injection_detector import scan_text_for_injections
from .risk_scorer import calculate_risk_score

def evaluate_proposal(
    context: ProposalContext,
    gemini_client: Optional[Any] = None,
) -> TrustDecision:
    """
    Pure, deterministic evaluation function for autonomous transaction proposals.
    Executes all 8 checks, advisory prompt-injection scanning, and risk scoring.
    Enforces strict decision priority:
      - HARD failures = BLOCKED
      - SOFT issues = NEEDS_HUMAN_APPROVAL (or BLOCKED per strict policy)
      - All pass = APPROVED (or NEEDS_HUMAN_APPROVAL per policy)
    Fail-closed: any runtime exception returns BLOCKED.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    checks: Dict[str, CheckResult] = {}
    reason_codes: List[ReasonCode] = []

    try:
        # Canonical bytes candidates for Ed25519 signature check
        candidate_bytes: List[bytes] = []
        if context.canonical_payload_bytes:
            candidate_bytes.append(context.canonical_payload_bytes)
        if context.proposal_payload_dict:
            candidate_bytes.append(
                json.dumps(context.proposal_payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
        if context.agent_signature:
            signing_dict = {
                "task_id": context.task_id,
                "amount": float(context.amount),
                "currency": context.currency,
                "provider": context.provider_name,
                "quote_id": context.quote_id or "",
            }
            candidate_bytes.append(
                json.dumps(signing_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )

        # ----------------------------------------------------------------------
        # Check 1: agent_authorization (HARD)
        # ----------------------------------------------------------------------
        res_agent = check_agent_authorization(
            agent_id=context.agent_id,
            agent_public_key=context.agent_public_key,
            agent_is_active=context.agent_is_active,
            agent_signature=context.agent_signature,
            canonical_payload_bytes=candidate_bytes if candidate_bytes else None,
        )
        checks[CheckType.AGENT_AUTHORIZATION.value] = res_agent
        if not res_agent.passed:
            reason_codes.extend(res_agent.reason_codes)

        # ----------------------------------------------------------------------
        # Check 2: task_linkage (HARD)
        # ----------------------------------------------------------------------
        res_task = check_task_linkage(
            task_id=context.task_id,
            task_exists=context.task_exists,
            user_id=context.user_id,
            task_owner_id=context.task_owner_id,
            task_is_active=context.task_is_active,
        )
        checks[CheckType.TASK_LINKAGE.value] = res_task
        if not res_task.passed:
            reason_codes.extend(res_task.reason_codes)

        # ----------------------------------------------------------------------
        # Check 3: task_relevance (SOFT)
        # ----------------------------------------------------------------------
        res_relevance = check_task_relevance(
            task_category=context.task_category,
            proposal_category=context.proposal_category,
            advisory_relevance_score=context.advisory_relevance_score or 1.0,
            min_relevance_threshold=0.5,
            strict_relevance=context.policy.strict_mode,
        )
        checks[CheckType.TASK_RELEVANCE.value] = res_relevance
        if not res_relevance.passed:
            reason_codes.extend(res_relevance.reason_codes)

        # ----------------------------------------------------------------------
        # Check 4: provider_allowlist (SOFT/HARD)
        # ----------------------------------------------------------------------
        res_provider = check_provider_allowlist(
            provider_name=context.provider_name,
            provider_url=context.provider_url,
            allowed_domains=context.policy.allowed_domains,
            blacklisted_domains=context.policy.blacklisted_domains,
            strict_mode=context.policy.strict_mode,
        )
        checks[CheckType.PROVIDER_ALLOWLIST.value] = res_provider
        if not res_provider.passed:
            reason_codes.extend(res_provider.reason_codes)

        # ----------------------------------------------------------------------
        # Check 5: quote_integrity (HARD)
        # ----------------------------------------------------------------------
        res_quote = check_quote_integrity(
            quote_id=context.quote_id,
            proposal_amount=context.amount,
            proposal_currency=context.currency,
            quote_amount=context.quote_amount,
            quote_currency=context.quote_currency,
            quote_expires_at=context.quote_expires_at,
            quote_hmac_signature=context.quote_hmac_signature,
            quote_hmac_secret=context.quote_hmac_secret,
            current_time_iso=now_iso,
            merchant_id=context.quote_merchant_id,
            payee_email=context.quote_payee_email,
        )
        checks[CheckType.QUOTE_INTEGRITY.value] = res_quote
        if not res_quote.passed:
            reason_codes.extend(res_quote.reason_codes)

        # ----------------------------------------------------------------------
        # Check 6: budget_limit (HARD)
        # ----------------------------------------------------------------------
        res_budget = check_budget_limit(
            proposal_amount=context.amount,
            task_budget_max=context.task_budget_max,
            current_committed_spend=context.current_committed_spend,
        )
        checks[CheckType.BUDGET_LIMIT.value] = res_budget
        if not res_budget.passed:
            reason_codes.extend(res_budget.reason_codes)

        # ----------------------------------------------------------------------
        # Check 7: approval_requirement (SOFT)
        # ----------------------------------------------------------------------
        res_approval = check_approval_requirement(
            proposal_amount=context.amount,
            auto_approve_threshold=context.policy.auto_approve_threshold,
            single_tx_limit=context.policy.single_tx_limit,
            human_approval_granted=context.human_approval_granted,
        )
        checks[CheckType.APPROVAL_REQUIREMENT.value] = res_approval
        if not res_approval.passed:
            reason_codes.extend(res_approval.reason_codes)

        # ----------------------------------------------------------------------
        # Check 8: replay_protection (HARD)
        # ----------------------------------------------------------------------
        res_replay = check_replay_protection(
            idempotency_key=context.idempotency_key,
            payload_hash=context.payload_hash,
            seen_idempotency_keys=context.seen_idempotency_keys,
            seen_payload_hashes=context.seen_payload_hashes,
        )
        checks[CheckType.REPLAY_PROTECTION.value] = res_replay
        if not res_replay.passed:
            reason_codes.extend(res_replay.reason_codes)

        # ----------------------------------------------------------------------
        # Advisory: Prompt-Injection Detector (Can ONLY raise severity)
        # ----------------------------------------------------------------------
        client_to_use = None if context.bypass_advisory_llm else gemini_client
        injection_res = scan_text_for_injections(
            justification=context.justification,
            fetched_page_text=context.fetched_page_text,
            gemini_client=client_to_use,
        )
        if injection_res.is_injection:
            reason_codes.append(ReasonCode.PROMPT_INJECTION_DETECTED)

        # ----------------------------------------------------------------------
        # Decision Synthesis & Priority Resolution
        # ----------------------------------------------------------------------
        has_hard_failure = any(not c.passed and c.severity == "HARD" for c in checks.values())
        has_soft_failure = any(not c.passed and c.severity == "SOFT" for c in checks.values())

        if has_hard_failure:
            decision = TrustDecisionEnum.BLOCKED
        elif injection_res.is_injection:
            # Advisory prompt injection elevates to NEEDS_HUMAN_APPROVAL or BLOCKED per strict mode
            decision = TrustDecisionEnum.BLOCKED if context.policy.strict_mode else TrustDecisionEnum.NEEDS_HUMAN_APPROVAL
        elif has_soft_failure:
            decision = TrustDecisionEnum.NEEDS_HUMAN_APPROVAL
        else:
            decision = TrustDecisionEnum.APPROVED

        # ----------------------------------------------------------------------
        # Risk Score Calculation (0 - 100)
        # ----------------------------------------------------------------------
        domain = extract_domain(context.provider_url)
        is_domain_allowlisted = (
            any(domain == a.lower() or domain.endswith(f".{a.lower()}") for a in context.policy.allowed_domains)
            if context.policy.allowed_domains and domain
            else False
        )
        is_domain_blacklisted = (
            any(domain == b.lower() or domain.endswith(f".{b.lower()}") for b in context.policy.blacklisted_domains)
            if context.policy.blacklisted_domains and domain
            else False
        )
        has_cat_match = bool(
            context.task_category
            and context.proposal_category
            and (context.task_category.lower() in context.proposal_category.lower() or context.proposal_category.lower() in context.task_category.lower())
        )

        risk_data = calculate_risk_score(
            amount=context.amount,
            task_budget_max=context.task_budget_max,
            current_committed_spend=context.current_committed_spend,
            single_tx_limit=context.policy.single_tx_limit,
            is_domain_allowlisted=is_domain_allowlisted,
            is_domain_blacklisted=is_domain_blacklisted,
            advisory_relevance_score=context.advisory_relevance_score or 1.0,
            has_category_match=has_cat_match,
            injection_flagged=injection_res.is_injection,
        )
        risk_score = risk_data["risk_score"]

        # Deduplicate reason codes in stable order
        unique_reason_codes: List[str] = []
        for rc in reason_codes:
            rc_val = rc.value if isinstance(rc, ReasonCode) else str(rc)
            if rc_val not in unique_reason_codes:
                unique_reason_codes.append(rc_val)

        # Plain-English Explanation
        explanation = _generate_explanation(decision, unique_reason_codes, context, checks)

        # SHA-256 Decision Preimage Hash
        preimage = {
            "task_id": context.task_id,
            "agent_id": context.agent_id,
            "amount": float(context.amount),
            "currency": context.currency,
            "provider": context.provider_name,
            "decision": decision.value,
            "reason_codes": unique_reason_codes,
            "risk_score": risk_score,
            "evaluated_at": now_iso,
            "policy_version": context.policy.policy_version,
        }
        decision_hash = hashlib.sha256(
            json.dumps(preimage, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        return TrustDecision(
            decision=decision,
            risk_score=risk_score,
            reason_codes=unique_reason_codes,
            explanation=explanation,
            checks=checks,
            checks_list=list(checks.values()),
            decision_hash=decision_hash,
            policy_version=context.policy.policy_version,
            evaluated_at=now_iso,
            eligible_for_human_review=(decision == TrustDecisionEnum.NEEDS_HUMAN_APPROVAL),
            proof={
                "sha256": decision_hash,
                "engine": "Nirbhar AI-TrustEngine-v2",
                "policy_version": context.policy.policy_version,
                "risk_breakdown": risk_data["breakdown"],
                "prompt_injection": injection_res.model_dump(),
            },
        )

    except Exception as e:
        # Rule 4: Fail-closed on any unexpected engine exception
        task_ref = getattr(context, "task_id", "unknown")
        policy_ver = getattr(getattr(context, "policy", None), "policy_version", "v1.0.0")
        fail_closed_hash = hashlib.sha256(f"FAIL_CLOSED:{task_ref}:{now_iso}:{str(e)}".encode("utf-8")).hexdigest()
        fallback_checks: Dict[str, CheckResult] = {}
        for ct in CheckType:
            fallback_checks[ct.value] = CheckResult(
                check_name=ct.value,
                passed=False,
                severity="HARD",
                impact=TrustDecisionEnum.BLOCKED,
                reason_codes=[ReasonCode.SYSTEM_ERROR],
                message=f"Engine runtime exception triggered fail-closed block: {str(e)}",
            )

        return TrustDecision(
            decision=TrustDecisionEnum.BLOCKED,
            risk_score=100.0,
            reason_codes=[ReasonCode.SYSTEM_ERROR.value],
            explanation=f"Transaction blocked by fail-closed safety guard due to internal engine error: {str(e)}",
            checks=fallback_checks,
            checks_list=list(fallback_checks.values()),
            decision_hash=fail_closed_hash,
            policy_version=policy_ver,
            evaluated_at=now_iso,
            eligible_for_human_review=False,
            proof={
                "sha256": fail_closed_hash,
                "engine": "Nirbhar AI-TrustEngine-v2-FailClosed",
                "error": str(e),
                "error_class": e.__class__.__name__,
            },
        )

def _generate_explanation(
    decision: TrustDecisionEnum,
    reason_codes: List[str],
    context: ProposalContext,
    checks: Dict[str, CheckResult],
) -> str:
    """Generates a clear, user-facing plain-English sentence explaining the decision."""
    if decision == TrustDecisionEnum.APPROVED:
        return (
            f"Transaction of ${float(context.amount):.2f} {context.currency} with {context.provider_name} "
            f"satisfies all 8 security rules and fits within remaining task budget."
        )

    if decision == TrustDecisionEnum.BLOCKED:
        if ReasonCode.BUDGET_EXCEEDED.value in reason_codes:
            return (
                f"Blocked: Proposed amount of ${float(context.amount):.2f} exceeds remaining budget "
                f"of ${(float(context.task_budget_max) - float(context.current_committed_spend)):.2f}."
            )
        if ReasonCode.QUOTE_EXPIRED.value in reason_codes:
            return f"Blocked: Quote '{context.quote_id}' has expired (TTL exceeded 10 minutes)."
        if ReasonCode.QUOTE_MISMATCH.value in reason_codes:
            return "Blocked: Quote HMAC signature verification failed or amount does not match authorized quote."
        if ReasonCode.AGENT_NOT_AUTHORIZED.value in reason_codes:
            return "Blocked: Proposing agent signature could not be verified against registered cryptographic keys."
        if ReasonCode.INVALID_TASK_REFERENCE.value in reason_codes:
            return f"Blocked: Task reference '{context.task_id}' is invalid, archived, or not owned by user."
        if ReasonCode.DUPLICATE_REQUEST.value in reason_codes:
            return "Blocked: Duplicate replay request detected (idempotency key or payload hash already executed)."
        return f"Blocked: Proposal violated security policies ({', '.join(reason_codes)})."

    # NEEDS_HUMAN_APPROVAL
    if ReasonCode.USER_APPROVAL_REQUIRED.value in reason_codes:
        return (
            f"Human approval required: Amount of ${float(context.amount):.2f} exceeds auto-approval threshold "
            f"of ${float(context.policy.auto_approve_threshold):.2f}."
        )
    if ReasonCode.PROVIDER_NOT_ALLOWLISTED.value in reason_codes:
        return f"Human approval required: Vendor '{context.provider_name}' is not currently in the pre-approved domain allowlist."
    if ReasonCode.TASK_MISMATCH.value in reason_codes:
        return f"Human approval required: Category mismatch or low relevance score detected for {context.provider_name}."
    if ReasonCode.PROMPT_INJECTION_DETECTED.value in reason_codes:
        return "Human approval required: Advisory scanner flagged potentially adversarial prompt-injection patterns in proposal."

    return f"Human review required based on policy checks ({', '.join(reason_codes)})."

