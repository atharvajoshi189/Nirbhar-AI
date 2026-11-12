import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.config import settings
from app.core.logging_config import setup_structured_logging
from app.core.sentry import init_sentry
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.rate_limit_and_idempotency import RateLimitAndIdempotencyMiddleware

from app.routers.health import router as health_router
from app.routers.audit import router as audit_router
from app.routers.agents import router as agents_router
from app.routers.tasks import router as tasks_router
from app.routers.transactions import router as transactions_router
from app.routers.trust import router as trust_router
from app.routers.stats import router as stats_router
from app.routers.webhooks import router as webhooks_router
from app.routers.red_team import router as red_team_router

load_dotenv()

# 1. Setup Structured JSON Logging (Phase 8 Item 2)
if settings.ENABLE_STRUCTURED_LOGGING:
    setup_structured_logging()

# 2. Setup Sentry Error Tracking & Performance (Phase 8 Item 2)
init_sentry(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Nirbhar AI Core API: Trust Engine, Spend Enforcement & Verification Layer"
)

# 3. Add Rate Limiting & Idempotency Cache Middleware (Redis backed)
app.add_middleware(
    RateLimitAndIdempotencyMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    idempotency_ttl=settings.IDEMPOTENCY_TTL_SECONDS
)

# 4. Add Request Context Middleware (Request IDs & Structured Access Telemetry)
app.add_middleware(RequestContextMiddleware)

# 5. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. Register Application Routers
app.include_router(health_router)
app.include_router(trust_router)
app.include_router(audit_router)
app.include_router(agents_router)
app.include_router(tasks_router)
app.include_router(transactions_router)
app.include_router(stats_router)
app.include_router(webhooks_router)
app.include_router(red_team_router)

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs"
    }
