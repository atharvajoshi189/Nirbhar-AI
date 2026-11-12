import os
import sys
import json
import pytest
from datetime import datetime, timezone

# Add api and root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_DIR = os.path.join(BASE_DIR, "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.services.audit import AuditChainService, GENESIS_PREV_HASH

@pytest.fixture
def audit_service():
    return AuditChainService(audit_secret="test_secret_nirbhar_2026")

def test_audit_chain_clean_verification(audit_service):
    """Rule 3: Clean sequential chain verified with 0 tampering."""
    events = []
    prev_h = GENESIS_PREV_HASH

    for i in range(1, 6):
        payload = {"action": f"EVENT_{i}", "amount": float(i * 10)}
        rec = audit_service.build_event(
            user_id="user_test_123",
            event_type=f"STEP_{i}",
            payload=payload,
            sequence_number=i,
            prev_hash=prev_h
        )
        prev_h = rec.hash
        events.append(rec.model_dump())

    res = audit_service.verify_chain(events)
    assert res.valid is True
    assert res.total_events == 5
    assert res.tampered_at_sequence is None
    assert res.latest_hash == prev_h

def test_audit_chain_detects_payload_tampering(audit_service):
    """Rule 3: Tampering with event payload breaks SHA-256 hash."""
    events = []
    prev_h = GENESIS_PREV_HASH

    for i in range(1, 4):
        payload = {"action": f"EVENT_{i}", "amount": 10.0}
        rec = audit_service.build_event(
            user_id="user_test_123",
            event_type=f"STEP_{i}",
            payload=payload,
            sequence_number=i,
            prev_hash=prev_h
        )
        prev_h = rec.hash
        events.append(rec.model_dump())

    # Tamper with event 2's payload
    events[1]["payload"]["amount"] = 9999.00

    res = audit_service.verify_chain(events)
    assert res.valid is False
    assert res.tampered_at_sequence == 2
    assert "Tamper detected at sequence 2" in (res.error_details or "")

def test_audit_chain_detects_broken_linkage(audit_service):
    """Rule 3: Tampering with prev_hash breaks backward linkage."""
    events = []
    prev_h = GENESIS_PREV_HASH

    for i in range(1, 4):
        payload = {"action": f"EVENT_{i}"}
        rec = audit_service.build_event(
            user_id="user_test_123",
            event_type=f"STEP_{i}",
            payload=payload,
            sequence_number=i,
            prev_hash=prev_h
        )
        prev_h = rec.hash
        events.append(rec.model_dump())

    # Break prev_hash on event 3
    events[2]["prev_hash"] = "f" * 64

    res = audit_service.verify_chain(events)
    assert res.valid is False
    assert res.tampered_at_sequence == 3
    assert "Hash linkage broken" in (res.error_details or "")

def test_audit_chain_detects_dropped_sequence(audit_service):
    """Rule 3: Dropping an event causes sequence discontinuity."""
    events = []
    prev_h = GENESIS_PREV_HASH

    for i in range(1, 5):
        payload = {"action": f"EVENT_{i}"}
        rec = audit_service.build_event(
            user_id="user_test_123",
            event_type=f"STEP_{i}",
            payload=payload,
            sequence_number=i,
            prev_hash=prev_h
        )
        prev_h = rec.hash
        events.append(rec.model_dump())

    # Drop event 2
    del events[1]

    res = audit_service.verify_chain(events)
    assert res.valid is False
    assert "Sequence discontinuity" in (res.error_details or "")

@pytest.mark.asyncio
async def test_live_audit_verify_api():
    """Verify FastAPI /audit/verify endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10.0) as client:
        res = await client.get("/audit/verify")
        assert res.status_code == 200
        data = res.json()
        assert "valid" in data
        assert "total_events" in data
        assert data["valid"] is True
        assert data["total_events"] > 0

@pytest.mark.asyncio
async def test_live_audit_events_pagination_api():
    """Verify FastAPI /audit/events paginated list endpoint."""
    from app.main import app
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10.0) as client:
        res = await client.get("/audit/events?limit=5&offset=0")
        assert res.status_code == 200
        data = res.json()
        assert "events" in data
        assert "total" in data
        assert len(data["events"]) <= 5
        assert data["total"] > 0
