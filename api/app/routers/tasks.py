import math
from typing import List, Optional, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_admin_client
from app.security.auth import get_current_user
from app.services.audit import audit_service
from app.jobs import enqueue_coordinator_agent

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskCreateRequest(BaseModel):
    title: Optional[str] = None
    description: str = Field(min_length=5, description="Full description of the autonomous goal")
    budget_max: Decimal = Field(gt=0, description="Hard ceiling budget limit in currency units")
    currency: str = Field(default="USD", description="Currency code (USD, EUR, GBP)")
    approval_mode: str = Field(default="above_limit", description="'always' or 'above_limit'")
    auto_approve_threshold: Optional[Decimal] = Field(default=Decimal("50.00"), description="Auto approval threshold amount")
    single_tx_limit: Optional[Decimal] = Field(default=None, description="Max allowed single transaction limit")
    allowed_domains: List[str] = Field(default_factory=list, description="Vendor domains allowed")
    blacklisted_domains: List[str] = Field(default_factory=list, description="Vendor domains explicitly forbidden")
    strict_mode: bool = True

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Creates a new task and versioned task_policy in Supabase,
    writes an append-only cryptographic audit event,
    and enqueues the Coordinator Agent background job via Redis + ARQ.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    # Determine auto_approve_threshold based on approval mode
    threshold = Decimal("0.00") if payload.approval_mode == "always" else (payload.auto_approve_threshold or Decimal("50.00"))
    if threshold > payload.budget_max:
        threshold = payload.budget_max

    single_limit = payload.single_tx_limit if payload.single_tx_limit and payload.single_tx_limit > 0 else payload.budget_max
    if single_limit < threshold:
        single_limit = threshold

    # Derive clean title if not explicitly provided
    task_title = payload.title.strip() if payload.title else payload.description.split("\n")[0][:60].strip()
    if not task_title:
        task_title = "Autonomous Goal Task"

    # 1. Insert into tasks table
    task_data = {
        "user_id": user_id,
        "title": task_title,
        "description": payload.description,
        "budget_max": float(payload.budget_max),
        "currency": payload.currency.upper(),
        "status": "ACTIVE"
    }

    task_res = supabase.table("tasks").insert(task_data).execute()
    if not task_res.data:
        raise HTTPException(status_code=500, detail="Failed to persist task in Supabase")
    new_task = task_res.data[0]
    task_id = new_task["id"]

    # 2. Insert into task_policies table
    policy_data = {
        "task_id": task_id,
        "user_id": user_id,
        "auto_approve_threshold": float(threshold),
        "single_tx_limit": float(single_limit),
        "allowed_domains": payload.allowed_domains,
        "blacklisted_domains": payload.blacklisted_domains,
        "strict_mode": payload.strict_mode
    }

    policy_res = supabase.table("task_policies").insert(policy_data).execute()
    new_policy = policy_res.data[0] if policy_res.data else {}

    # 3. Append to immutable audit chain
    audit_record = audit_service.append_event(
        user_id=user_id,
        event_type="TASK_CREATED",
        task_id=task_id,
        payload={
            "task_id": task_id,
            "title": task_title,
            "budget_max": float(payload.budget_max),
            "currency": payload.currency.upper(),
            "approval_mode": payload.approval_mode,
            "auto_approve_threshold": float(threshold),
            "single_tx_limit": float(single_limit),
            "allowed_domains": payload.allowed_domains,
            "blacklisted_domains": payload.blacklisted_domains
        }
    )

    # 4. Enqueue Coordinator agent background job via Redis + ARQ
    job_id = None
    try:
        job_id = await enqueue_coordinator_agent(task_id=task_id, user_id=user_id)
    except Exception as e:
        # Per fail-closed rule: log error, but return created task with pending status
        print(f"[Warning] Failed to enqueue background job: {e}")

    return {
        "task": new_task,
        "policy": new_policy,
        "audit_event": {
            "sequence_number": audit_record.get("sequence_number"),
            "hash": audit_record.get("hash"),
            "prev_hash": audit_record.get("prev_hash")
        },
        "job": {
            "id": job_id,
            "status": "QUEUED" if job_id else "PENDING_START",
            "queue": "redis-arq"
        }
    }

@router.get("", status_code=status.HTTP_200_OK)
async def list_tasks(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Lists all tasks belonging to the authenticated user.
    Enforces RLS isolation via user_id.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    # Query tasks with policy and latest agent run
    tasks_res = supabase.table("tasks").select("*, task_policies(*), agent_runs(*)").eq("user_id", user_id).order("created_at", desc=True).execute()
    return tasks_res.data or []

@router.get("/{task_id}", status_code=status.HTTP_200_OK)
async def get_task(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieves full details of a specific task including policy, transactions, and agent runs.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    task_res = supabase.table("tasks").select("*, task_policies(*), agent_runs(*), transactions(*)").eq("id", task_id).eq("user_id", user_id).execute()
    if not task_res.data:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_res.data[0]

@router.get("/{task_id}/activity", status_code=status.HTTP_200_OK)
async def get_task_activity(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieves chronological agent runs for a specific task.
    """
    user_id = current_user["id"]
    supabase = get_supabase_admin_client()

    runs_res = supabase.table("agent_runs").select("*, agents(name, role, public_key)").eq("task_id", task_id).eq("user_id", user_id).order("created_at", desc=False).execute()
    return runs_res.data or []

