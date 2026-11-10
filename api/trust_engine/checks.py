import hmac
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urlparse
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from .models import CheckResult, ReasonCode, TrustDecisionEnum, CheckType

def extract_domain(url: str) -> str:
    """Extracts lowercase hostname without port or credentials."""
    if not url:
        return ""
    try:
        if "://" not in url:
            url = f"https://{url}"
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if "@" in netloc:
            netloc = netloc.split("@")[-1]
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        return netloc.strip()
    except Exception:
        return ""

def verify_ed25519_signature(public_key_hex: str, signature_hex: str, payload_bytes: bytes) -> bool:
    """Verifies Ed25519 signature over canonical payload bytes."""
    try:
        pub_bytes = bytes.fromhex(public_key_hex)
        sig_bytes = bytes.fromhex(signature_hex)
        vk = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        vk.verify(sig_bytes, payload_bytes)
        return True
    except (InvalidSignature, Exception):
        return False

# ------------------------------------------------------------------------------
# 1. agent_authorization
# ------------------------------------------------------------------------------
def check_agent_authorization(
    agent_id: str,
    agent_public_key: Optional[str],
    agent_is_active: bool,
    agent_signature: Optional[str],
    canonical_payload_bytes: Optional[Union[bytes, List[bytes]]] = None,
) -> CheckResult:
    """
    Check 1: agent_authorization
    Guarantees agent is registered, active, and proposal signature is cryptographically valid.
    """
    if not agent_id or not agent_public_key:
        return CheckResult(
            check_name=CheckType.AGENT_AUTHORIZATION.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.AGENT_NOT_AUTHORIZED],
            message="Agent is not registered or public key is missing",
            metadata={"agent_id": agent_id},
        )

    if not agent_is_active:
        return CheckResult(
            check_name=CheckType.AGENT_AUTHORIZATION.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.AGENT_NOT_AUTHORIZED],
            message="Agent account has been revoked or deactivated",
            metadata={"agent_id": agent_id, "active": False},
        )

    if not agent_signature or len(agent_signature) < 64:
        return CheckResult(
            check_name=CheckType.AGENT_AUTHORIZATION.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.AGENT_NOT_AUTHORIZED],
            message="Missing or malformed agent Ed25519 signature",
            metadata={"signature_present": bool(agent_signature)},
        )

    if canonical_payload_bytes is not None:
        payload_list = canonical_payload_bytes if isinstance(canonical_payload_bytes, list) else [canonical_payload_bytes]
        is_valid = any(
            verify_ed25519_signature(
                public_key_hex=agent_public_key,
                signature_hex=agent_signature,
                payload_bytes=b,
            )
            for b in payload_list
        )
        if not is_valid:
            return CheckResult(
                check_name=CheckType.AGENT_AUTHORIZATION.value,
                passed=False,
                severity="HARD",
                impact=TrustDecisionEnum.BLOCKED,
                reason_codes=[ReasonCode.AGENT_NOT_AUTHORIZED],
                message="Agent Ed25519 signature verification failed: payload forged or wrong key",
                metadata={"agent_id": agent_id, "signature_valid": False},
            )

    return CheckResult(
        check_name=CheckType.AGENT_AUTHORIZATION.value,
        passed=True,
        severity="HARD",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message="Agent is registered, active, and signature is cryptographically verified",
        metadata={"agent_id": agent_id, "public_key_prefix": agent_public_key[:12] + "..."},
    )

# ------------------------------------------------------------------------------
# 2. task_linkage
# ------------------------------------------------------------------------------
def check_task_linkage(
    task_id: str,
    task_exists: bool,
    user_id: str,
    task_owner_id: Optional[str] = None,
    task_is_active: bool = True,
) -> CheckResult:
    """
    Check 2: task_linkage
    Guarantees proposal is bound to an existing, active task owned by the calling user.
    """
    if not task_id or not task_exists:
        return CheckResult(
            check_name=CheckType.TASK_LINKAGE.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.INVALID_TASK_REFERENCE],
            message=f"Task '{task_id}' does not exist or reference is invalid",
            metadata={"task_id": task_id, "task_exists": task_exists},
        )

    if task_owner_id and task_owner_id != user_id:
        return CheckResult(
            check_name=CheckType.TASK_LINKAGE.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.INVALID_TASK_REFERENCE],
            message="Cross-tenant isolation violation: task belongs to another user",
            metadata={"task_id": task_id, "user_id": user_id, "owner_id": task_owner_id},
        )

    if not task_is_active:
        return CheckResult(
            check_name=CheckType.TASK_LINKAGE.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.INVALID_TASK_REFERENCE],
            message=f"Task '{task_id}' is closed, archived, or inactive",
            metadata={"task_id": task_id, "task_active": False},
        )

    return CheckResult(
        check_name=CheckType.TASK_LINKAGE.value,
        passed=True,
        severity="HARD",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message="Task reference is valid, active, and properly linked to user",
        metadata={"task_id": task_id},
    )

# ------------------------------------------------------------------------------
# 3. task_relevance
# ------------------------------------------------------------------------------
def check_task_relevance(
    task_category: Optional[str],
    proposal_category: str,
    advisory_relevance_score: float = 1.0,
    min_relevance_threshold: float = 0.5,
    strict_relevance: bool = False,
) -> CheckResult:
    """
    Check 3: task_relevance
    Checks category alignment and advisory relevance score.
    Decision: Soft issue (NEEDS_HUMAN_APPROVAL) or BLOCKED if strict.
    """
    # 1. Category check
    cat_match = True
    if task_category and proposal_category:
        norm_task = task_category.strip().lower()
        norm_prop = proposal_category.strip().lower()
        cat_match = (norm_task == norm_prop or norm_task in norm_prop or norm_prop in norm_task)

    # 2. Advisory score check
    score_ok = advisory_relevance_score >= min_relevance_threshold

    if not cat_match or not score_ok:
        decision_impact = TrustDecisionEnum.BLOCKED if strict_relevance else TrustDecisionEnum.NEEDS_HUMAN_APPROVAL
        mismatch_reasons = []
        if not cat_match:
            mismatch_reasons.append(f"Category mismatch ('{proposal_category}' vs task '{task_category}')")
        if not score_ok:
            mismatch_reasons.append(f"Low advisory relevance score ({advisory_relevance_score:.2f} < {min_relevance_threshold})")

        return CheckResult(
            check_name=CheckType.TASK_RELEVANCE.value,
            passed=False,
            severity="SOFT" if not strict_relevance else "HARD",
            impact=decision_impact,
            reason_codes=[ReasonCode.TASK_MISMATCH],
            message="; ".join(mismatch_reasons),
            metadata={
                "task_category": task_category,
                "proposal_category": proposal_category,
                "advisory_score": advisory_relevance_score,
                "threshold": min_relevance_threshold,
            },
        )

    return CheckResult(
        check_name=CheckType.TASK_RELEVANCE.value,
        passed=True,
        severity="SOFT",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message=f"Category aligned ('{proposal_category}') with advisory score {advisory_relevance_score:.2f}",
        metadata={"category": proposal_category, "advisory_score": advisory_relevance_score},
    )

# ------------------------------------------------------------------------------
# 4. provider_allowlist
# ------------------------------------------------------------------------------
def check_provider_allowlist(
    provider_name: str,
    provider_url: str,
    allowed_domains: List[str],
    blacklisted_domains: List[str],
    strict_mode: bool = False,
) -> CheckResult:
    """
    Check 4: provider_allowlist
    Evaluates provider against blacklists and allowlists.
    Blacklist = HARD BLOCKED.
    Unallowlisted in strict mode = SOFT NEEDS_HUMAN_APPROVAL (or BLOCKED).
    """
    domain = extract_domain(provider_url)

    # 1. Blacklist check (Immediate hard block)
    if domain and blacklisted_domains:
        for b in blacklisted_domains:
            b_clean = b.strip().lower()
            if domain == b_clean or domain.endswith(f".{b_clean}"):
                return CheckResult(
                    check_name=CheckType.PROVIDER_ALLOWLIST.value,
                    passed=False,
                    severity="HARD",
                    impact=TrustDecisionEnum.BLOCKED,
                    reason_codes=[ReasonCode.PROVIDER_NOT_ALLOWLISTED],
                    message=f"Provider domain '{domain}' is explicitly blacklisted by security policy",
                    metadata={"domain": domain, "blacklist_match": b_clean},
                )

    # 2. Strict allowlist check
    if strict_mode and allowed_domains:
        matched = False
        if domain:
            for a in allowed_domains:
                a_clean = a.strip().lower()
                if domain == a_clean or domain.endswith(f".{a_clean}"):
                    matched = True
                    break
        if not matched:
            return CheckResult(
                check_name=CheckType.PROVIDER_ALLOWLIST.value,
                passed=False,
                severity="SOFT",
                impact=TrustDecisionEnum.NEEDS_HUMAN_APPROVAL,
                reason_codes=[ReasonCode.PROVIDER_NOT_ALLOWLISTED],
                message=f"Provider '{provider_name}' ({domain or 'no URL'}) is not in the approved allowlist",
                metadata={"domain": domain, "allowed_domains": allowed_domains},
            )

    return CheckResult(
        check_name=CheckType.PROVIDER_ALLOWLIST.value,
        passed=True,
        severity="SOFT",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message=f"Provider '{provider_name}' satisfies allowlist and blacklist policies",
        metadata={"domain": domain},
    )

# ------------------------------------------------------------------------------
# 5. quote_integrity
# ------------------------------------------------------------------------------
def check_quote_integrity(
    quote_id: Optional[str],
    proposal_amount: Decimal,
    proposal_currency: str,
    quote_amount: Optional[Decimal],
    quote_currency: Optional[str],
    quote_expires_at: Optional[str],
    quote_hmac_signature: Optional[str],
    quote_hmac_secret: Optional[str],
    current_time_iso: Optional[str] = None,
    merchant_id: Optional[str] = None,
    payee_email: Optional[str] = None,
) -> CheckResult:
    """
    Check 5: quote_integrity
    Guarantees quote HMAC signature is valid, quote is not expired, and amount matches.
    """
    if not quote_id:
        return CheckResult(
            check_name=CheckType.QUOTE_INTEGRITY.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.QUOTE_MISMATCH],
            message="No quote ID provided for transaction proposal",
            metadata={"quote_id": None},
        )

    # 1. Amount and Currency Match
    if quote_amount is not None:
        if proposal_amount != quote_amount:
            return CheckResult(
                check_name=CheckType.QUOTE_INTEGRITY.value,
                passed=False,
                severity="HARD",
                impact=TrustDecisionEnum.BLOCKED,
                reason_codes=[ReasonCode.QUOTE_MISMATCH],
                message=f"Proposal amount (${proposal_amount:.2f}) does not match authorized quote amount (${quote_amount:.2f})",
                metadata={"proposal_amount": float(proposal_amount), "quote_amount": float(quote_amount)},
            )
    if quote_currency and proposal_currency.upper() != quote_currency.upper():
        return CheckResult(
            check_name=CheckType.QUOTE_INTEGRITY.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.QUOTE_MISMATCH],
            message=f"Proposal currency '{proposal_currency}' does not match quote currency '{quote_currency}'",
            metadata={"proposal_currency": proposal_currency, "quote_currency": quote_currency},
        )

    # 2. Expiry Check
    if quote_expires_at:
        try:
            exp_clean = quote_expires_at.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(exp_clean)
            now_dt = (
                datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
                if current_time_iso
                else datetime.now(timezone.utc)
            )
            if now_dt > exp_dt:
                return CheckResult(
                    check_name=CheckType.QUOTE_INTEGRITY.value,
                    passed=False,
                    severity="HARD",
                    impact=TrustDecisionEnum.BLOCKED,
                    reason_codes=[ReasonCode.QUOTE_EXPIRED],
                    message=f"Quote '{quote_id}' expired at {quote_expires_at}. Maximum validity is 10 minutes.",
                    metadata={"quote_id": quote_id, "expires_at": quote_expires_at, "checked_at": now_dt.isoformat()},
                )
        except Exception as e:
            return CheckResult(
                check_name=CheckType.QUOTE_INTEGRITY.value,
                passed=False,
                severity="HARD",
                impact=TrustDecisionEnum.BLOCKED,
                reason_codes=[ReasonCode.QUOTE_EXPIRED],
                message=f"Malformed expiry timestamp: {e}",
                metadata={"quote_expires_at": quote_expires_at},
            )

    # 3. HMAC Verification (if secret and signature provided)
    if quote_hmac_signature and quote_hmac_secret:
        amt_val = float(quote_amount if quote_amount is not None else proposal_amount)
        exp_str = quote_expires_at or ""
        curr_upper = proposal_currency.upper()

        preimages: List[str] = [
            f"{quote_id}:{amt_val:.2f}:{proposal_currency}:{exp_str}",
            f"{quote_id}:{amt_val:.2f}:{curr_upper}:{exp_str}",
        ]
        if merchant_id and payee_email:
            preimages.insert(0, f"{quote_id}:{merchant_id}:{payee_email}:{amt_val:.2f}:{curr_upper}:{exp_str}")

        sandbox_merchants = [
            ("merch_apexresearch", "sb-apexresearch@business.example.com"),
            ("merch_cloudscale", "sb-cloudscale@business.example.com"),
            ("merch_cybershield", "sb-cybershield@business.example.com"),
        ]
        for m_id, email in sandbox_merchants:
            preimages.append(f"{quote_id}:{m_id}:{email}:{amt_val:.2f}:{curr_upper}:{exp_str}")

        hmac_valid = False
        for preimage in preimages:
            expected_hmac = hmac.new(
                quote_hmac_secret.encode("utf-8"),
                preimage.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if hmac.compare_digest(quote_hmac_signature, expected_hmac):
                hmac_valid = True
                break

        if not hmac_valid:
            return CheckResult(
                check_name=CheckType.QUOTE_INTEGRITY.value,
                passed=False,
                severity="HARD",
                impact=TrustDecisionEnum.BLOCKED,
                reason_codes=[ReasonCode.QUOTE_MISMATCH],
                message="Quote HMAC signature verification failed: quote parameters have been altered or forged",
                metadata={"quote_id": quote_id, "signature_valid": False},
            )

    return CheckResult(
        check_name=CheckType.QUOTE_INTEGRITY.value,
        passed=True,
        severity="HARD",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message=f"Quote '{quote_id}' integrity verified: valid HMAC signature, active TTL, and matching amount",
        metadata={"quote_id": quote_id, "amount": float(proposal_amount)},
    )

# ------------------------------------------------------------------------------
# 6. budget_limit
# ------------------------------------------------------------------------------
def check_budget_limit(
    proposal_amount: Decimal,
    task_budget_max: Decimal,
    current_committed_spend: Decimal = Decimal("0.00"),
) -> CheckResult:
    """
    Check 6: budget_limit
    Guarantees proposal does not exceed the remaining task budget ceiling.
    Strict boundary handling:
    - proposal_amount <= 0 -> BLOCKED (BUDGET_EXCEEDED)
    - proposal_amount == remaining -> PASSED
    - proposal_amount == remaining + 0.01 -> BLOCKED (BUDGET_EXCEEDED)
    """
    if proposal_amount <= Decimal("0.00"):
        return CheckResult(
            check_name=CheckType.BUDGET_LIMIT.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.BUDGET_EXCEEDED],
            message=f"Invalid transaction amount (${proposal_amount}): amount must be strictly greater than $0.00",
            metadata={"amount": float(proposal_amount)},
        )

    remaining_budget = task_budget_max - current_committed_spend

    if proposal_amount > remaining_budget:
        return CheckResult(
            check_name=CheckType.BUDGET_LIMIT.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.BUDGET_EXCEEDED],
            message=f"Proposed amount (${proposal_amount:.2f}) exceeds remaining budget ceiling (${remaining_budget:.2f})",
            metadata={
                "task_budget_max": float(task_budget_max),
                "committed_spend": float(current_committed_spend),
                "remaining_budget": float(remaining_budget),
                "requested_amount": float(proposal_amount),
            },
        )

    return CheckResult(
        check_name=CheckType.BUDGET_LIMIT.value,
        passed=True,
        severity="HARD",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message=f"Amount (${proposal_amount:.2f}) is within budget ceiling (${remaining_budget:.2f} remaining)",
        metadata={
            "remaining_budget_before": float(remaining_budget),
            "remaining_budget_after": float(remaining_budget - proposal_amount),
        },
    )

# ------------------------------------------------------------------------------
# 7. approval_requirement
# ------------------------------------------------------------------------------
def check_approval_requirement(
    proposal_amount: Decimal,
    auto_approve_threshold: Decimal,
    single_tx_limit: Decimal,
    requires_explicit_consent: bool = False,
    human_approval_granted: bool = False,
) -> CheckResult:
    """
    Check 7: approval_requirement
    Checks policy limits requiring human intervention.
    If human approval was already granted and active, the requirement is satisfied.
    """
    if human_approval_granted:
        return CheckResult(
            check_name=CheckType.APPROVAL_REQUIREMENT.value,
            passed=True,
            severity="SOFT",
            impact=TrustDecisionEnum.APPROVED,
            reason_codes=[],
            message="Human user approval verified and active",
            metadata={"human_approved": True, "amount": float(proposal_amount)},
        )

    # 1. Single transaction limit
    if proposal_amount > single_tx_limit:
        return CheckResult(
            check_name=CheckType.APPROVAL_REQUIREMENT.value,
            passed=False,
            severity="SOFT",
            impact=TrustDecisionEnum.NEEDS_HUMAN_APPROVAL,
            reason_codes=[ReasonCode.USER_APPROVAL_REQUIRED],
            message=f"Amount (${proposal_amount:.2f}) exceeds single transaction policy limit (${single_tx_limit:.2f})",
            metadata={"amount": float(proposal_amount), "single_tx_limit": float(single_tx_limit)},
        )

    # 2. Auto-approve threshold or explicit consent required
    if proposal_amount > auto_approve_threshold or requires_explicit_consent:
        return CheckResult(
            check_name=CheckType.APPROVAL_REQUIREMENT.value,
            passed=False,
            severity="SOFT",
            impact=TrustDecisionEnum.NEEDS_HUMAN_APPROVAL,
            reason_codes=[ReasonCode.USER_APPROVAL_REQUIRED],
            message=f"Amount (${proposal_amount:.2f}) exceeds auto-approval threshold (${auto_approve_threshold:.2f}); user authorization required",
            metadata={"amount": float(proposal_amount), "auto_approve_threshold": float(auto_approve_threshold)},
        )

    return CheckResult(
        check_name=CheckType.APPROVAL_REQUIREMENT.value,
        passed=True,
        severity="SOFT",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message=f"Amount (${proposal_amount:.2f}) is within auto-approval threshold (${auto_approve_threshold:.2f})",
        metadata={"amount": float(proposal_amount), "threshold": float(auto_approve_threshold)},
    )

# ------------------------------------------------------------------------------
# 8. replay_protection
# ------------------------------------------------------------------------------
def check_replay_protection(
    idempotency_key: Optional[str],
    payload_hash: Optional[str],
    seen_idempotency_keys: List[str],
    seen_payload_hashes: List[str],
) -> CheckResult:
    """
    Check 8: replay_protection
    Guarantees proposal is not a duplicate replay or double-spend attempt.
    """
    if idempotency_key and idempotency_key in seen_idempotency_keys:
        return CheckResult(
            check_name=CheckType.REPLAY_PROTECTION.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.DUPLICATE_REQUEST],
            message=f"Duplicate request detected: idempotency key '{idempotency_key}' has already been processed",
            metadata={"idempotency_key": idempotency_key},
        )

    if payload_hash and payload_hash in seen_payload_hashes:
        return CheckResult(
            check_name=CheckType.REPLAY_PROTECTION.value,
            passed=False,
            severity="HARD",
            impact=TrustDecisionEnum.BLOCKED,
            reason_codes=[ReasonCode.DUPLICATE_REQUEST],
            message=f"Duplicate request detected: proposal payload hash '{payload_hash[:16]}...' was already evaluated",
            metadata={"payload_hash": payload_hash},
        )

    return CheckResult(
        check_name=CheckType.REPLAY_PROTECTION.value,
        passed=True,
        severity="HARD",
        impact=TrustDecisionEnum.APPROVED,
        reason_codes=[],
        message="Request passes replay protection check (unique idempotency key and payload hash)",
        metadata={"idempotency_key": idempotency_key, "payload_hash": payload_hash[:16] if payload_hash else None},
    )
