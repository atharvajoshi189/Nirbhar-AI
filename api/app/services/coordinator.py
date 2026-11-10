import os
import json
import time
from typing import List, Optional, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, ValidationError
from google import genai
from google.genai import types

from app.config import settings
from app.db.supabase import get_supabase_admin_client
from app.security.agent_keys import agent_key_manager
from app.services.audit import audit_service

class SubtaskPlan(BaseModel):
    title: str = Field(description="One-line actionable title for this subtask")
    description: str = Field(description="Detailed requirement and operational scope")
    service_category: str = Field(description="Service category e.g. cloud_compute, api_credits, domain_registration, web_hosting, security, data_storage")
    allocated_budget: float = Field(description="Allocated budget in USD for this subtask. Must be strictly positive.")
    target_vendor_hint: Optional[str] = Field(default=None, description="Suggested or standard vendor name for this category (e.g. Cloudflare, AWS, OpenAI, Namecheap)")

class CoordinatorPlan(BaseModel):
    summary: str = Field(description="Executive summary of the decomposed execution plan")
    total_budget: float = Field(description="Sum of all allocated budgets. Must be less than or equal to the task budget.")
    subtasks: List[SubtaskPlan] = Field(description="Ordered list of subtasks required to fulfill the user task")

def ensure_user_agent(supabase_client, user_id: str, role: str = "coordinator") -> str:
    """
    Ensures an agent record exists in the agents table for this user and role.
    Returns the agent UUID.
    """
    res = supabase_client.table("agents").select("id").eq("user_id", user_id).eq("role", role).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]

    public_keys = agent_key_manager.get_public_keys()
    public_key = public_keys.get(role, "")

    role_names = {
        "coordinator": "Nirbhar Coordinator Agent",
        "research": "Nirbhar Research Agent",
        "service": "Nirbhar Service Procurement Agent"
    }

    insert_res = supabase_client.table("agents").insert({
        "user_id": user_id,
        "name": role_names.get(role, f"Agent-{role}"),
        "role": role,
        "public_key": public_key,
        "is_active": True
    }).execute()

    return insert_res.data[0]["id"]

class CoordinatorService:
    def __init__(self):
        self.model_name = "models/gemini-3.5-flash-lite"

    def get_client(self) -> genai.Client:
        key = settings.active_gemini_key
        if not key or key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured in .env. Rule 1: No simulation.")
        return genai.Client(api_key=key)

    def execute_plan_generation(self, task_id: str, user_id: str) -> Dict[str, Any]:
        """
        Executes real Gemini API call with structured output to plan the task.
        Saves full telemetry into agent_runs and audit_events.
        """
        supabase = get_supabase_admin_client()
        client = self.get_client()

        # 1. Fetch authoritative task record
        task_res = supabase.table("tasks").select("*").eq("id", task_id).eq("user_id", user_id).execute()
        if not task_res.data:
            raise ValueError(f"Task {task_id} not found for user {user_id}")
        task = task_res.data[0]

        # 2. Ensure coordinator agent exists
        agent_id = ensure_user_agent(supabase, user_id, role="coordinator")

        # 3. Create initial agent_run record with status STARTED
        run_record = supabase.table("agent_runs").insert({
            "task_id": task_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "model_name": self.model_name,
            "status": "STARTED",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 0.0,
            "output_payload": {"stage": "PLANNING_INITIALIZED", "description": task.get("description", "")}
        }).execute()
        run_id = run_record.data[0]["id"]

        # 4. Construct prompt
        system_instruction = (
            "You are the Nirbhar AI Coordinator Agent, an expert autonomous task decomposition system. "
            "Your objective is to analyze the user's task description and hard budget constraint, and decompose it "
            "into a minimal, highly structured execution plan of distinct subtasks. "
            "Each subtask must have a clear title, operational description, standard service category, "
            "suggested target vendor, and allocated budget in USD. "
            f"The total allocated budget of all subtasks combined MUST NOT exceed ${task['budget_max']:.2f} USD. "
            "All subtask allocated budgets must be positive and mathematically realistic."
        )

        user_content = (
            f"Task Title: {task.get('title', 'N/A')}\n"
            f"Task Description: {task.get('description', '')}\n"
            f"Maximum Budget Ceiling: ${task['budget_max']} {task.get('currency', 'USD')}\n\n"
            "Generate the structured execution plan adhering strictly to the schema."
        )

        full_prompt = f"{system_instruction}\n\n{user_content}"

        # 5. Execute Gemini call with 1 retry on invalid output
        max_attempts = 2
        last_error = None
        plan_dict = None
        usage_data = None
        latency_ms = 0.0

        for attempt in range(1, max_attempts + 1):
            start_time = time.perf_counter()
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CoordinatorPlan,
                        temperature=0.2,
                    ),
                )
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

                # Parse and strictly validate with Pydantic
                raw_text = response.text or "{}"
                validated_plan = CoordinatorPlan.model_validate_json(raw_text)

                # Mathematical invariant check: total budget must not exceed task max budget
                if validated_plan.total_budget > float(task["budget_max"]):
                    # Clamp/adjust if model was slightly off
                    scaling_factor = float(task["budget_max"]) / validated_plan.total_budget
                    for st in validated_plan.subtasks:
                        st.allocated_budget = round(st.allocated_budget * scaling_factor, 2)
                    validated_plan.total_budget = round(sum(st.allocated_budget for st in validated_plan.subtasks), 2)

                plan_dict = validated_plan.model_dump()
                usage_data = response.usage_metadata
                break

            except (ValidationError, Exception) as e:
                last_error = e
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                if attempt < max_attempts:
                    time.sleep(1.0)
                    continue

        if not plan_dict:
            # Mark agent_run as FAILED
            error_payload = {
                "error": str(last_error),
                "error_type": last_error.__class__.__name__ if last_error else "UnknownError",
                "attempts": max_attempts,
                "prompt": full_prompt
            }
            supabase.table("agent_runs").update({
                "status": "FAILED",
                "latency_ms": latency_ms,
                "output_payload": error_payload
            }).eq("id", run_id).execute()

            raise RuntimeError(f"Coordinator agent failed to produce a valid plan after {max_attempts} attempts: {last_error}")

        # 6. Sign output with Coordinator's Ed25519 private key
        signature = agent_key_manager.sign_proposal(role="coordinator", payload=plan_dict)

        prompt_tokens = getattr(usage_data, "prompt_token_count", 0) if usage_data else 0
        completion_tokens = getattr(usage_data, "candidates_token_count", 0) if usage_data else 0

        # 7. Update agent_run with COMPLETED status and full proof telemetry
        final_payload = {
            "plan": plan_dict,
            "raw_prompt": full_prompt,
            "model": self.model_name,
            "latency_ms": latency_ms,
            "tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens
            },
            "signature": signature
        }

        supabase.table("agent_runs").update({
            "status": "COMPLETED",
            "model_name": self.model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
            "signature": signature,
            "output_payload": final_payload
        }).eq("id", run_id).execute()

        # 8. Record audit event for Coordinator Plan Generation
        audit_service.append_event(
            user_id=user_id,
            event_type="AGENT_COORDINATOR_PLAN_GENERATED",
            task_id=task_id,
            payload={
                "run_id": run_id,
                "agent_role": "coordinator",
                "model_name": self.model_name,
                "latency_ms": latency_ms,
                "tokens": prompt_tokens + completion_tokens,
                "subtasks_count": len(plan_dict.get("subtasks", [])),
                "allocated_budget": plan_dict.get("total_budget"),
                "signature": signature
            }
        )

        return {
            "run_id": run_id,
            "task_id": task_id,
            "status": "COMPLETED",
            "model": self.model_name,
            "latency_ms": latency_ms,
            "plan": plan_dict,
            "signature": signature
        }

coordinator_service = CoordinatorService()

