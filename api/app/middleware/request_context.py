import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.access")

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware managing request IDs and structured access logging:
    - Injects unique X-Request-ID into request state and response headers.
    - Measures wall-clock execution latency.
    - Emits structured JSON access logs with request_id and latency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # 1. Resolve or Generate Request ID
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = f"req_{uuid.uuid4().hex[:12]}"
        
        request.state.request_id = req_id

        # 2. Process Request
        try:
            response = await call_next(request)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "Unhandled error processing %s %s: %s",
                request.method, request.url.path, str(exc),
                extra={
                    "request_id": req_id,
                    "telemetry": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": 500,
                        "latency_ms": latency_ms,
                    }
                },
                exc_info=True
            )
            raise exc

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 3. Attach Response Headers
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = str(latency_ms)

        # 4. Structured Access Log
        # Skip logging health checks in access logs to avoid disk clutter
        if request.url.path != "/health":
            logger.info(
                "%s %s -> %d (%0.2fms)",
                request.method, request.url.path, response.status_code, latency_ms,
                extra={
                    "request_id": req_id,
                    "telemetry": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "latency_ms": latency_ms,
                        "client_ip": request.client.host if request.client else "unknown",
                    }
                }
            )

        return response

