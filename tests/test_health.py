import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add api directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.main import app

@pytest.mark.asyncio
async def test_health_endpoint_schema_and_pings():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data
        assert "proof" in data
        
        services = data["services"]
        assert "gemini" in services
        assert "supabase" in services
        assert "paypal" in services
        
        # Verify proof metadata
        assert "sha256" in data["proof"]
        assert len(data["proof"]["sha256"]) == 64
        
        # Verify services have real status
        for svc_name in ["gemini", "supabase", "paypal"]:
            svc = services[svc_name]
            assert svc["status"] in ["operational", "degraded", "error", "unconfigured"]
            assert "name" in svc

