import time
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/health", tags=["Health"])

class ServiceHealth(BaseModel):
    name: str
    status: str  # "operational" | "degraded" | "error" | "unconfigured"
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = {}

class SystemHealthResponse(BaseModel):
    status: str  # "operational" | "degraded" | "unhealthy"
    timestamp: str
    environment: str
    services: Dict[str, ServiceHealth]
    proof: Dict[str, Any]

async def check_gemini() -> ServiceHealth:
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        return ServiceHealth(
            name="Google Gemini",
            status="unconfigured",
            message="GEMINI_API_KEY is not configured in .env",
            metadata={"hint": "Set GEMINI_API_KEY in .env"}
        )
    
    start = time.perf_counter()
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])[:5]]
                return ServiceHealth(
                    name="Google Gemini",
                    status="operational",
                    latency_ms=latency,
                    message="Connected and authenticated with Gemini API",
                    metadata={"sample_models": models, "http_status": 200}
                )
            else:
                return ServiceHealth(
                    name="Google Gemini",
                    status="error",
                    latency_ms=latency,
                    message=f"Gemini API returned status {resp.status_code}: {resp.text[:100]}",
                    metadata={"http_status": resp.status_code}
                )
    except Exception as e:
        latency = round((time.perf_counter() - start) * 1000, 2)
        return ServiceHealth(
            name="Google Gemini",
            status="error",
            latency_ms=latency,
            message=f"Connection failed: {str(e)}",
            metadata={"error": str(e)}
        )

async def check_supabase() -> ServiceHealth:
    url = settings.SUPABASE_URL
    anon_key = settings.SUPABASE_ANON_KEY
    
    if not url or not anon_key or "your-project" in url or "your_supabase" in anon_key:
        return ServiceHealth(
            name="Supabase",
            status="unconfigured",
            message="SUPABASE_URL or SUPABASE_ANON_KEY not configured in .env",
            metadata={"hint": "Set SUPABASE_URL and SUPABASE_ANON_KEY in .env"}
        )
    
    start = time.perf_counter()
    try:
        rest_url = f"{url.rstrip('/')}/rest/v1/"
        headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}"
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(rest_url, headers=headers)
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code in (200, 404):  # Root REST schema endpoint returns OpenAPI or 200
                return ServiceHealth(
                    name="Supabase",
                    status="operational",
                    latency_ms=latency,
                    message="Connected to Supabase REST engine",
                    metadata={"endpoint": rest_url, "http_status": resp.status_code}
                )
            else:
                return ServiceHealth(
                    name="Supabase",
                    status="error",
                    latency_ms=latency,
                    message=f"Supabase returned status {resp.status_code}: {resp.text[:100]}",
                    metadata={"http_status": resp.status_code}
                )
    except Exception as e:
        latency = round((time.perf_counter() - start) * 1000, 2)
        return ServiceHealth(
            name="Supabase",
            status="error",
            latency_ms=latency,
            message=f"Connection failed: {str(e)}",
            metadata={"error": str(e)}
        )

async def check_paypal() -> ServiceHealth:
    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    base_url = settings.PAYPAL_API_BASE
    
    if not client_id or not client_secret or "your_paypal" in client_id or "your_paypal" in client_secret:
        return ServiceHealth(
            name="PayPal Sandbox",
            status="unconfigured",
            message="PAYPAL_CLIENT_ID or PAYPAL_CLIENT_SECRET not configured in .env",
            metadata={"environment": settings.PAYPAL_ENVIRONMENT, "base_url": base_url}
        )
    
    start = time.perf_counter()
    try:
        token_url = f"{base_url.rstrip('/')}/v1/oauth2/token"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                token_url,
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json", "Accept-Language": "en_US"}
            )
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code == 200:
                data = resp.json()
                return ServiceHealth(
                    name="PayPal Sandbox",
                    status="operational",
                    latency_ms=latency,
                    message="OAuth 2.0 client credentials authenticated successfully",
                    metadata={
                        "app_id": data.get("app_id"),
                        "token_type": data.get("token_type"),
                        "expires_in": data.get("expires_in"),
                        "http_status": 200
                    }
                )
            else:
                return ServiceHealth(
                    name="PayPal Sandbox",
                    status="error",
                    latency_ms=latency,
                    message=f"PayPal OAuth failed with status {resp.status_code}: {resp.text[:100]}",
                    metadata={"http_status": resp.status_code}
                )
    except Exception as e:
        latency = round((time.perf_counter() - start) * 1000, 2)
        return ServiceHealth(
            name="PayPal Sandbox",
            status="error",
            latency_ms=latency,
            message=f"Connection failed: {str(e)}",
            metadata={"error": str(e)}
        )

@router.get("", response_model=SystemHealthResponse)
async def get_system_health():
    now_iso = datetime.now(timezone.utc).isoformat()
    
    gemini_health = await check_gemini()
    supabase_health = await check_supabase()
    paypal_health = await check_paypal()
    
    services = {
        "gemini": gemini_health,
        "supabase": supabase_health,
        "paypal": paypal_health,
    }
    
    statuses = [s.status for s in services.values()]
    if all(s == "operational" for s in statuses):
        overall_status = "operational"
    elif any(s == "error" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"
        
    payload_str = json.dumps({k: v.model_dump() for k, v in services.items()}, sort_keys=True)
    proof_hash = hashlib.sha256(f"{now_iso}:{payload_str}".encode()).hexdigest()
    
    return SystemHealthResponse(
        status=overall_status,
        timestamp=now_iso,
        environment=settings.ENVIRONMENT,
        services=services,
        proof={
            "sha256": proof_hash,
            "verified_at": now_iso,
            "engine": "Nirbhar AI-HealthEngine-v1"
        }
    )

