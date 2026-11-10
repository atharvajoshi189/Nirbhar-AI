from decimal import Decimal
from typing import Dict, Any, Optional

def calculate_risk_score(
    amount: Decimal,
    task_budget_max: Decimal,
    current_committed_spend: Decimal,
    single_tx_limit: Decimal,
    is_domain_allowlisted: bool,
    is_domain_blacklisted: bool,
    advisory_relevance_score: float,
    has_category_match: bool,
    injection_flagged: bool,
) -> Dict[str, Any]:
    """
    Computes a deterministic 0-100 risk score with documented weights.
    Weights Breakdown:
    - Budget Utilization (Max 30 pts): ratio of proposal to total task budget
    - Provider Reputation / Allowlist (Max 20 pts): known vs unknown/blacklisted
    - Task Relevance & Alignment (Max 20 pts): category match & advisory score
    - Adversarial / Injection Suspicion (Max 20 pts): prompt injection signal
    - Single Transaction Magnitude (Max 10 pts): ratio to single_tx_limit
    Total Max: 100 points.
    NOTE: Hard rules always override this score.
    """
    points_budget = 0.0
    points_domain = 0.0
    points_relevance = 0.0
    points_injection = 0.0
    points_tx_limit = 0.0

    # 1. Budget Utilization (Max 30 pts)
    remaining_budget = max(task_budget_max - current_committed_spend, Decimal("0.00"))
    if remaining_budget > 0:
        utilization = float(amount / remaining_budget)
        if utilization <= 0.25:
            points_budget = 5.0
        elif utilization <= 0.50:
            points_budget = 10.0
        elif utilization <= 0.75:
            points_budget = 20.0
        else:
            points_budget = 30.0
    else:
        points_budget = 30.0

    # 2. Provider Domain (Max 20 pts)
    if is_domain_blacklisted:
        points_domain = 20.0
    elif not is_domain_allowlisted:
        points_domain = 12.0
    else:
        points_domain = 0.0

    # 3. Task Relevance (Max 20 pts)
    if not has_category_match:
        points_relevance += 10.0
    if advisory_relevance_score < 0.6:
        points_relevance += 10.0
    elif advisory_relevance_score < 0.85:
        points_relevance += 5.0

    # 4. Prompt Injection (Max 20 pts)
    if injection_flagged:
        points_injection = 20.0

    # 5. Single Tx Limit Magnitude (Max 10 pts)
    if single_tx_limit > 0:
        tx_ratio = float(amount / single_tx_limit)
        if tx_ratio > 1.0:
            points_tx_limit = 10.0
        elif tx_ratio > 0.5:
            points_tx_limit = 5.0
        else:
            points_tx_limit = 0.0

    total_score = round(points_budget + points_domain + points_relevance + points_injection + points_tx_limit, 1)
    clamped_score = min(max(total_score, 0.0), 100.0)

    breakdown = {
        "budget_utilization_pts": points_budget,
        "provider_domain_pts": points_domain,
        "task_relevance_pts": points_relevance,
        "injection_pts": points_injection,
        "tx_limit_pts": points_tx_limit,
    }

    return {
        "risk_score": clamped_score,
        "breakdown": breakdown,
    }

