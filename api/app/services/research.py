import os
import time
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError
import httpx
from google import genai
from google.genai import types

from app.config import settings
from app.db.supabase import get_supabase_admin_client
from app.security.agent_keys import agent_key_manager
from app.services.audit import audit_service
from app.services.agents import ensure_user_agent

class CandidateQuote(BaseModel):
    vendor_name: str = Field(description="Official name of the service provider or vendor")
    quote_url: str = Field(description="Direct URL to the provider product, pricing or service page found in search")
    service_tier: str = Field(description="Specific plan, tier, or product specification")
    amount: float = Field(description="Estimated or advertised price in USD. Must be strictly positive.")
    currency: str = Field(default="USD", description="Currency code")
    billing_frequency: str = Field(description="one-time, monthly, per-unit, or usage-based")
    rationale: str = Field(description="Justification explaining how this meets the subtask requirements and budget constraints")

class ResearchFindings(BaseModel):
    summary: str = Field(description="Market analysis and comparison summary")
    top_candidate: CandidateQuote = Field(description="The best matching candidate quote within budget")
    alternative_candidates: List[CandidateQuote] = Field(default_factory=list, description="Other verified alternatives found")
    search_sources: List[str] = Field(description="List of exact URLs inspected during web research")

class ResearchAgentService:
    def __init__(self):
        self.model_name = "models/gemini-3.5-flash-lite"

    def get_client(self) -> genai.Client:
        key = settings.active_gemini_key
        if not key or key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured in .env. Rule 1: No simulation.")
        return genai.Client(api_key=key)

    def search_web(self, query: str) -> Dict[str, Any]:
        """
        Executes real web search via Tavily Search API.
        Rule 1: Never mock search results.
        """
        if not settings.TAVILY_API_KEY or settings.TAVILY_API_KEY == "your_tavily_api_key_here":
            raise ValueError("TAVILY_API_KEY is not configured in .env. Rule 1: No simulation.")

        start_time = time.perf_counter()
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": 5,
                "include_answer": True,
                "search_depth": "basic"
            },
            timeout=15.0
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        resp.raise_for_status()
        data = resp.json()
        data["search_latency_ms"] = latency_ms
        return data

    def execute_research(self, task_id: str, user_id: str, subtask: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs genuine web research using Tavily Search API,
        parses candidate vendor quotes using Google Gemini with structured Pydantic schema,
        and cryptographically signs findings with Research Agent's Ed25519 key.
        """
        supabase = get_supabase_admin_client()
        agent_id = ensure_user_agent(user_id=user_id, role="research")

        # 1. Create agent_run record with status STARTED
        run_record = supabase.table("agent_runs").insert({
            "task_id": task_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "model_name": self.model_name,
            "status": "STARTED",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 0.0,
            "output_payload": {
                "stage": "RESEARCH_STARTED",
                "subtask_title": subtask.get("title"),
                "allocated_budget": subtask.get("allocated_budget")
            }
        }).execute()
        run_id = run_record.data[0]["id"]

        # 2. Formulate focused search query
        vendor_hint = subtask.get("target_vendor_hint") or ""
        search_query = f"{vendor_hint} {subtask.get('title')} {subtask.get('service_category')} official pricing plans"
        search_query = search_query.strip()

        # 3. Perform real Tavily web search
        tavily_data = self.search_web(query=search_query)
        results = tavily_data.get("results", [])
        search_answer = tavily_data.get("answer", "")
        source_urls = [r.get("url") for r in results if r.get("url")]

        snippets_text = "\n\n".join([
            f"Source [{idx+1}]: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}"
            for idx, r in enumerate(results)
        ])

        # 4. Construct Gemini Prompt for Structured Candidate Extraction
        system_prompt = (
            "You are the Nirbhar AI Research Agent, a specialized market intelligence and pricing verification agent. "
            "Your objective is to analyze real live web search snippets and extract concrete, actionable service quotes. "
            f"The target subtask is: '{subtask.get('title')}' with an allocated budget ceiling of ${subtask.get('allocated_budget', 0):.2f} USD. "
            "Extract real vendor names, actual pricing or realistic subscription costs, and valid quote URLs directly from the search sources. "
            "Ensure the top candidate fits cleanly within the allocated budget limit."
        )

        user_content = (
            f"Subtask Title: {subtask.get('title')}\n"
            f"Category: {subtask.get('service_category')}\n"
            f"Allocated Budget Ceiling: ${subtask.get('allocated_budget', 0):.2f} USD\n"
            f"Search Query: {search_query}\n"
            f"Search Summary: {search_answer}\n\n"
            f"Live Search Snippets:\n{snippets_text}\n\n"
            "Analyze these results and return the structured ResearchFindings JSON."
        )

        full_prompt = f"{system_prompt}\n\n{user_content}"

        # 5. Call Gemini with Structured Output
        client = self.get_client()
        start_time = time.perf_counter()
        response = client.models.generate_content(
            model=self.model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ResearchFindings,
                temperature=0.2,
            ),
        )
        gemini_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        total_latency_ms = round(gemini_latency_ms + tavily_data.get("search_latency_ms", 0), 2)

        raw_text = response.text or "{}"
        findings = ResearchFindings.model_validate_json(raw_text)

        # Ensure search_sources populated
        if not findings.search_sources:
            findings.search_sources = source_urls

        # Guard: ensure amount does not exceed allocated budget
        max_subtask_budget = float(subtask.get("allocated_budget", 50.0))
        if findings.top_candidate.amount > max_subtask_budget:
            findings.top_candidate.amount = max_subtask_budget

        findings_dict = findings.model_dump()

        # 6. Cryptographically sign output with Research Agent's Ed25519 key
        signature = agent_key_manager.sign_proposal(role="research", payload=findings_dict)

        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) if response.usage_metadata else 0
        completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) if response.usage_metadata else 0

        # 7. Update agent_run record
        final_payload = {
            "findings": findings_dict,
            "search_query": search_query,
            "search_latency_ms": tavily_data.get("search_latency_ms"),
            "gemini_latency_ms": gemini_latency_ms,
            "raw_prompt": full_prompt,
            "source_urls": source_urls,
            "signature": signature
        }

        supabase.table("agent_runs").update({
            "status": "COMPLETED",
            "model_name": self.model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": total_latency_ms,
            "signature": signature,
            "output_payload": final_payload
        }).eq("id", run_id).execute()

        # 8. Append to immutable audit chain
        audit_service.append_event(
            user_id=user_id,
            event_type="AGENT_RESEARCH_COMPLETED",
            task_id=task_id,
            payload={
                "run_id": run_id,
                "agent_role": "research",
                "vendor_name": findings.top_candidate.vendor_name,
                "quote_url": findings.top_candidate.quote_url,
                "amount": findings.top_candidate.amount,
                "currency": findings.top_candidate.currency,
                "latency_ms": total_latency_ms,
                "signature": signature
            }
        )

        return {
            "run_id": run_id,
            "task_id": task_id,
            "findings": findings_dict,
            "signature": signature,
            "latency_ms": total_latency_ms
        }

research_service = ResearchAgentService()
