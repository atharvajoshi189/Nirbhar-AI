import time
import json
import logging
from typing import Callable
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response as StarletteResponse

from app.core.redis_client import redis_manager
from app.config import settings

logger = logging.getLogger("api.middleware")

class RateLimitAndIdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware providing:
    1. Redis-backed rate limiting with sliding 60-second window.
    2. Redis-backed idempotency caching for mutating requests with Idempotency-Key.
    """

    def __init__(self, app, requests_per_minute: int = 240, idempotency_ttl: int = 86400):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.idempotency_ttl = idempotency_ttl

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 1. Skip rate-limiting for health and docs
        if path in ("/health", "/", "/docs", "/openapi.json", "/redoc", "/favicon.ico"):
            return await call_next(request)

        # 2. Derive Client Identifier (API Key or Client IP)
        auth_hdr = request.headers.get("Authorization") or ""
        client_ip = request.client.host if request.client else "unknown"
        client_id = f"user_{auth_hdr[-12:]}" if len(auth_hdr) > 12 else f"ip_{client_ip}"

        # 3. Rate Limiting Check
        current_minute = int(time.time() // 60)
        rate_key = f"ratelimit:{client_id}:{current_minute}"
        
        current_count = await redis_manager.incr(rate_key)
        if current_count == 1:
            await redis_manager.expire(rate_key, 65)

        remaining = max(0, self.requests_per_minute - current_count)

        if current_count > self.requests_per_minute:
            logger.warning(
                "Rate limit exceeded for %s on %s (%d/%d)",
                client_id, path, current_count, self.requests_per_minute
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate Limit Exceeded",
                    "detail": f"Allowed maximum {self.requests_per_minute} requests per minute.",
                    "retry_after_seconds": 60
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0"
                }
            )

        # 4. Idempotency Check for Mutating Calls
        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
        is_mutating = request.method in ("POST", "PUT", "PATCH")

        if is_mutating and idempotency_key:
            cache_key = f"idempotency:{request.method}:{path}:{idempotency_key}"
            cached_data = await redis_manager.get(cache_key)

            if cached_data:
                try:
                    cached_entry = json.loads(cached_data)
                    logger.info("Idempotency cache hit for key %s", idempotency_key)
                    
                    headers = dict(cached_entry.get("headers", {}))
                    headers["X-Idempotency-Replay"] = "true"
                    headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
                    headers["X-RateLimit-Remaining"] = str(remaining)

                    return StarletteResponse(
                        content=cached_entry.get("body", "").encode("utf-8"),
                        status_code=cached_entry.get("status_code", 200),
                        headers=headers,
                        media_type="application/json"
                    )
                except Exception as e:
                    logger.error("Failed to parse cached idempotency entry: %s", e)

        # 5. Process Request
        response = await call_next(request)

        # 6. Attach Rate Limit Headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        # 7. Cache Successful Mutating Response under Idempotency Key
        if is_mutating and idempotency_key and response.status_code < 400:
            try:
                # Capture body
                response_body = [chunk async for chunk in response.body_iterator]
                response.body_iterator = iterate_in_chunks(response_body)
                body_str = b"".join(response_body).decode("utf-8")

                cached_entry = {
                    "status_code": response.status_code,
                    "headers": {k: v for k, v in response.headers.items() if k.lower() in ("content-type",)},
                    "body": body_str,
                    "cached_at": time.time()
                }
                cache_key = f"idempotency:{request.method}:{path}:{idempotency_key}"
                await redis_manager.set(cache_key, json.dumps(cached_entry), ex=self.idempotency_ttl)
                response.headers["X-Idempotency-Key"] = idempotency_key
            except Exception as e:
                logger.error("Failed to cache idempotency response: %s", e)

        return response

async def iterate_in_chunks(chunks):
    for c in chunks:
        yield c

