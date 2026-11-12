import time
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.core.redis_client import redis_manager

SERVER_START_TIME = time.time()

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
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    environment: str
    services: Dict[str, ServiceHealth]
    proof: Dict[str, Any]

async def check_gemini() -> ServiceHealth:
    api_key = settings.active_gemini_key
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
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    
    if not url or not key or "your-project" in url or "your_supabase" in key:
        return ServiceHealth(
            name="Supabase",
            status="unconfigured",
            message="SUPABASE_URL or keys not configured in .env",
            metadata={"hint": "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env"}
        )
    
    start = time.perf_counter()
    try:
        rest_url = f"{url.rstrip('/')}/rest/v1/"
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}"
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(rest_url, headers=headers)
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code in (200, 404):
                return ServiceHealth(
                    name="Supabase",
                    status="operational",
                    latency_ms=latency,
                    message="Connected and authenticated with Supabase REST engine",
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

async def check_redis() -> ServiceHealth:
    start = time.perf_counter()
    try:
        is_ok = await redis_manager.is_healthy()
        latency = round((time.perf_counter() - start) * 1000, 2)
        if is_ok:
            return ServiceHealth(
                name="Redis",
                status="operational",
                latency_ms=latency,
                message="Connected to Redis cache and rate limiter",
                metadata={"url": settings.REDIS_URL}
            )
        else:
            return ServiceHealth(
                name="Redis",
                status="degraded",
                latency_ms=latency,
                message="Using in-memory fallback rate-limiter and cache",
                metadata={"mode": "in-memory-fallback"}
            )
    except Exception as e:
        latency = round((time.perf_counter() - start) * 1000, 2)
        return ServiceHealth(
            name="Redis",
            status="degraded",
            latency_ms=latency,
            message=f"Redis check fallback: {str(e)}",
            metadata={"error": str(e)}
        )

@router.get("", response_model=SystemHealthResponse)
async def get_system_health():
    now_iso = datetime.now(timezone.utc).isoformat()
    uptime_sec = round(time.time() - SERVER_START_TIME, 2)
    
    gemini_health = await check_gemini()
    supabase_health = await check_supabase()
    paypal_health = await check_paypal()
    redis_health = await check_redis()
    
    services = {
        "gemini": gemini_health,
        "supabase": supabase_health,
        "paypal": paypal_health,
        "redis": redis_health,
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
        uptime_seconds=uptime_sec,
        environment=settings.ENVIRONMENT,
        services=services,
        proof={
            "sha256": proof_hash,
            "verified_at": now_iso,
            "uptime_seconds": uptime_sec,
            "engine": "Nirbhar AI-HealthEngine-v2"
        }
    )

@router.post("/kill-gemini-key")
async def kill_gemini_key():
    settings.kill_gemini_key()
    return {"status": "gemini_key_killed", "active_key": settings.active_gemini_key}

@router.post("/restore-gemini-key")
async def restore_gemini_key():
    settings.restore_gemini_key()
    return {"status": "gemini_key_restored", "active_key": settings.active_gemini_key[:12] + "..." if settings.active_gemini_key else None}
