from typing import Dict, Any
from fastapi import APIRouter, Depends
from app.db.supabase import get_supabase_admin_client
from app.security.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("", status_code=200)
async def get_dashboard_stats(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Returns the 3 key metric stats for the authenticated user's dashboard:
    1. Total tasks count
    2. Total approved spend (sum of APPROVED/COMPLETED transactions)
    3. Blocked transactions count
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    # 1. Total tasks count
    tasks_res = supabase.table("tasks").select("id", count="exact").eq("user_id", user_id).execute()
    tasks_count = tasks_res.count if tasks_res.count is not None else len(tasks_res.data or [])

    # 2. Query transactions for user
    tx_res = supabase.table("transactions").select("amount, status").eq("user_id", user_id).execute()
    transactions = tx_res.data or []

    approved_spend = 0.0
    blocked_count = 0

    for tx in transactions:
        status = tx.get("status")
        amt = float(tx.get("amount", 0.0))
        if status in ("APPROVED", "COMPLETED", "EXECUTING"):
            approved_spend += amt
        elif status == "BLOCKED":
            blocked_count += 1

    return {
        "tasks_count": tasks_count,
        "total_approved_spend": round(approved_spend, 2),
        "blocked_count": blocked_count,
        "currency": "USD"
    }

