import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.agent_keys import AGENT_ROLES

@pytest.mark.asyncio
async def test_agent_public_keys_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/agents/keys")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["algorithm"] == "Ed25519"
        assert set(data["public_keys"].keys()) == set(AGENT_ROLES)
        for role, key in data["public_keys"].items():
            assert len(key) == 64

@pytest.mark.asyncio
async def test_agent_verify_signature_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        from app.security.agent_keys import agent_key_manager
        payload = {"item": "GPU Cloud Compute", "cost": 150.0}
        sig = agent_key_manager.sign_proposal("coordinator", payload)

        # Valid signature
        res = await ac.post("/agents/verify-signature", json={
            "role": "coordinator",
            "payload": payload,
            "signature": sig
        })
        assert res.status_code == 200
        assert res.json()["valid"] is True

        # Invalid/tampered payload
        res_tampered = await ac.post("/agents/verify-signature", json={
            "role": "coordinator",
            "payload": {"item": "GPU Cloud Compute", "cost": 999.0},
            "signature": sig
        })
        assert res_tampered.status_code == 200
        assert res_tampered.json()["valid"] is False

