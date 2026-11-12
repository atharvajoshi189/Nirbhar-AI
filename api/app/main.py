import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.config import settings
from app.routers.health import router as health_router
from app.routers.audit import router as audit_router
from app.routers.agents import router as agents_router
from app.routers.tasks import router as tasks_router
from app.routers.transactions import router as transactions_router
from app.routers.stats import router as stats_router
from app.routers.webhooks import router as webhooks_router
from app.routers.red_team import router as red_team_router

load_dotenv()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Nirbhar AI Core API: Trust Engine & Verification Layer"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
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

