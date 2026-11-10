import pytest
from app.security.agent_keys import AgentKeyManager, AGENT_ROLES

@pytest.fixture
def key_manager(tmp_path):
    storage_file = str(tmp_path / "agent_keys_test.json")
    return AgentKeyManager(storage_path=storage_file)

def test_agent_roles_generated(key_manager):
    public_keys = key_manager.get_public_keys()
    assert set(public_keys.keys()) == set(AGENT_ROLES)
    for role in AGENT_ROLES:
        key_hex = public_keys[role]
        assert len(key_hex) == 64  # Ed25519 public key is 32 bytes (64 hex characters)

def test_sign_and_verify_proposal(key_manager):
    proposal = {
        "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
        "agent_role": "coordinator",
        "vendor": "Tavily Search API",
        "amount": 25.00,
        "currency": "USD"
    }

    # Coordinator signs proposal
    signature = key_manager.sign_proposal("coordinator", proposal)
    assert len(signature) == 128  # Ed25519 signature is 64 bytes (128 hex chars)

    coord_pub = key_manager.get_public_keys()["coordinator"]
    is_valid = key_manager.verify_signature(coord_pub, proposal, signature)
    assert is_valid is True

def test_tampered_proposal_fails_verification(key_manager):
    proposal = {
        "task_id": "test-task",
        "vendor": "Valid Provider",
        "amount": 10.00
    }
    signature = key_manager.sign_proposal("service", proposal)
    pub_key = key_manager.get_public_keys()["service"]

    # Tamper with amount
    tampered_proposal = dict(proposal)
    tampered_proposal["amount"] = 999.00

    is_valid = key_manager.verify_signature(pub_key, tampered_proposal, signature)
    assert is_valid is False

def test_wrong_agent_key_fails_verification(key_manager):
    proposal = {"task_id": "task-abc", "amount": 15.0}
    # Signed by 'research'
    signature = key_manager.sign_proposal("research", proposal)

    # Attempt to verify with 'coordinator' public key
    coord_pub = key_manager.get_public_keys()["coordinator"]
    is_valid = key_manager.verify_signature(coord_pub, proposal, signature)
    assert is_valid is False

