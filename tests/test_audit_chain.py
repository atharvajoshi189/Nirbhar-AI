import pytest
from app.services.audit import AuditChainService, GENESIS_PREV_HASH

@pytest.fixture
def audit_service():
    return AuditChainService(audit_secret="test_secret_salt_12345")

def test_empty_audit_chain(audit_service):
    res = audit_service.verify_chain([])
    assert res.valid is True
    assert res.total_events == 0
    assert res.latest_hash is None

def test_valid_audit_chain(audit_service):
    user_id = "user-uuid-1"
    events = []
    
    # Event 1: Genesis block
    e1 = audit_service.build_event(
        user_id=user_id,
        event_type="TASK_CREATED",
        payload={"task_id": "t-1", "budget_max": 250.0},
        sequence_number=1,
        prev_hash=None
    )
    events.append(e1.model_dump())
    
    # Event 2
    e2 = audit_service.build_event(
        user_id=user_id,
        event_type="PROPOSAL_RECEIVED",
        payload={"quote_id": "q-1", "amount": 45.0, "vendor": "API Provider"},
        sequence_number=2,
        prev_hash=e1.hash
    )
    events.append(e2.model_dump())
    
    # Event 3
    e3 = audit_service.build_event(
        user_id=user_id,
        event_type="TRUST_DECISION_EVALUATED",
        payload={"decision": "APPROVED", "risk_score": 0.05},
        sequence_number=3,
        prev_hash=e2.hash
    )
    events.append(e3.model_dump())
    
    # Verify whole chain
    res = audit_service.verify_chain(events)
    assert res.valid is True
    assert res.total_events == 3
    assert res.latest_hash == e3.hash
    assert res.tampered_at_sequence is None

def test_tamper_detection_modified_payload(audit_service):
    user_id = "user-uuid-1"
    events = []
    
    e1 = audit_service.build_event(
        user_id=user_id,
        event_type="TASK_CREATED",
        payload={"task_id": "t-1", "budget_max": 100.0},
        sequence_number=1,
    )
    events.append(e1.model_dump())
    
    e2 = audit_service.build_event(
        user_id=user_id,
        event_type="PROPOSAL_RECEIVED",
        payload={"amount": 50.0},
        sequence_number=2,
        prev_hash=e1.hash
    )
    events.append(e2.model_dump())
    
    # Adversary tampers with amount in event 2 (from 50.0 to 5000.0)
    events[1]["payload"]["amount"] = 5000.0
    
    # Recomputed chain MUST detect tamper
    res = audit_service.verify_chain(events)
    assert res.valid is False
    assert res.tampered_at_sequence == 2
    assert "Tamper detected at sequence 2" in res.error_details

def test_tamper_detection_broken_hash_link(audit_service):
    user_id = "user-uuid-1"
    events = []
    
    e1 = audit_service.build_event(user_id=user_id, event_type="E1", payload={"data": 1}, sequence_number=1)
    events.append(e1.model_dump())
    
    e2 = audit_service.build_event(user_id=user_id, event_type="E2", payload={"data": 2}, sequence_number=2, prev_hash=e1.hash)
    events.append(e2.model_dump())
    
    # Adversary alters prev_hash in event 2
    events[1]["prev_hash"] = "deadbeef" * 8
    
    res = audit_service.verify_chain(events)
    assert res.valid is False
    assert res.tampered_at_sequence == 2
    assert "Hash linkage broken at sequence 2" in res.error_details

def test_tamper_detection_missing_sequence(audit_service):
    user_id = "user-uuid-1"
    events = []
    
    e1 = audit_service.build_event(user_id=user_id, event_type="E1", payload={"k": 1}, sequence_number=1)
    events.append(e1.model_dump())
    
    e2 = audit_service.build_event(user_id=user_id, event_type="E2", payload={"k": 2}, sequence_number=2, prev_hash=e1.hash)
    
    e3 = audit_service.build_event(user_id=user_id, event_type="E3", payload={"k": 3}, sequence_number=3, prev_hash=e2.hash)
    events.append(e3.model_dump()) # Skipping e2
    
    res = audit_service.verify_chain(events)
    assert res.valid is False
    assert "Sequence discontinuity" in res.error_details
