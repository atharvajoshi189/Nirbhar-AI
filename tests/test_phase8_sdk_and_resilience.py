import os
import sys
import uuid
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vendor-gateway"))

import agenttrust
from agenttrust.crypto import generate_keypair, sign_payload, verify_signature
from app.main import app as core_api_app

client = TestClient(core_api_app)

def test_sdk_keypair_generation():
    """Requirement 1: SDK generates valid Ed25519 keypairs."""
    priv, pub = generate_keypair()
    assert isinstance(priv, str) and len(priv) == 64
    assert isinstance(pub, str) and len(pub) == 64
    assert priv != pub

def test_sdk_proposal_signing_and_tamper_detection():
    """Requirement 1: Cryptographic signing and tamper prevention."""
    priv, pub = generate_keypair()
    proposal = {
        "amount": 15.00,
        "currency": "USD",
        "provider_name": "CloudScale Infrastructure Solutions",
        "provider_url": "https://cloudscale.io/api",
        "justification": "Procure dedicated build agent"
    }

    signed = agenttrust.sign(proposal, key=priv)
    assert "signature" in signed
    assert "signer_pubkey" in signed
    assert "signed_at" in signed
    assert signed["signer_pubkey"] == pub

    # Verify signature holds for untouched proposal
    is_valid = verify_signature(signed, signed["signature"], signed["signer_pubkey"])
    assert is_valid is True

    # Tampering: attacker changes amount to 500.00
    tampered = dict(signed)
    tampered["amount"] = 500.00
    is_valid_tampered = verify_signature(tampered, tampered["signature"], tampered["signer_pubkey"])
    assert is_valid_tampered is False

def test_trust_verify_api_endpoint():
    """Requirement 1: Real /trust/verify API endpoint evaluates proposals."""
    priv, pub = generate_keypair()
    proposal = {
        "amount": 12.00,
        "currency": "USD",
        "provider_name": "CloudScale Infrastructure Solutions",
        "provider_url": "https://cloudscale.io/api",
        "proposal_category": "cloud_compute",
        "justification": "Autonomous indexing capacity expansion",
        "signer_pubkey": pub,
        "bypass_advisory_llm": True
    }
    signed = agenttrust.sign(proposal, key=priv)

    res = client.post("/trust/verify", json=signed)
    assert res.status_code == 200
    data = res.json()
    assert "decision" in data
    assert "risk_score" in data
    assert "reason_codes" in data
    assert "proof_chip" in data
    assert data["proof_chip"]["sha256"] is not None
    assert "X-Request-ID" in res.headers
    assert "X-Response-Time-Ms" in res.headers

def test_idempotency_cache():
    """Requirement 2: Redis/in-memory idempotency cache deduplicates mutating calls."""
    priv, pub = generate_keypair()
    idempotency_key = f"idem_{uuid.uuid4().hex}"
    proposal = {
        "amount": 10.00,
        "currency": "USD",
        "provider_name": "CloudScale Infrastructure Solutions",
        "provider_url": "https://cloudscale.io/api",
        "proposal_category": "cloud_compute",
        "justification": "Idempotent payment test",
        "signer_pubkey": pub,
        "bypass_advisory_llm": True
    }

    # First Call
    res1 = client.post(
        "/trust/verify",
        json=proposal,
        headers={"Idempotency-Key": idempotency_key}
    )
    assert res1.status_code == 200
    assert "X-Idempotency-Replay" not in res1.headers

    # Second Call with identical Idempotency-Key
    res2 = client.post(
        "/trust/verify",
        json=proposal,
        headers={"Idempotency-Key": idempotency_key}
    )
    assert res2.status_code == 200
    assert res2.headers.get("X-Idempotency-Replay") == "true"
    assert res1.json() == res2.json()

def test_request_id_and_rate_limit_headers():
    """Requirement 2: Structured request IDs and rate limiting telemetry headers."""
    custom_req_id = f"custom_req_{uuid.uuid4().hex[:8]}"
    res = client.get("/health", headers={"X-Request-ID": custom_req_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_req_id
    assert "X-Response-Time-Ms" in res.headers

def test_health_endpoint_uptime_and_redis():
    """Requirement 4: Core API /health endpoint returns uptime and component statuses."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0.0
    assert "services" in data
    assert "redis" in data["services"]
    assert "gemini" in data["services"]
    assert "supabase" in data["services"]
    assert "paypal" in data["services"]

def test_vendor_gateway_health():
    """Requirement 4: Vendor Gateway /health endpoint returns uptime and merchants."""
    import importlib.util
    vg_spec = importlib.util.spec_from_file_location(
        "vg_main",
        os.path.join(os.path.dirname(__file__), "..", "vendor-gateway", "app", "main.py")
    )
    vg_mod = importlib.util.module_from_spec(vg_spec)
    vg_spec.loader.exec_module(vg_mod)
    vg_client = TestClient(vg_mod.app)

    res = vg_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "operational"
    assert "uptime_seconds" in data
    assert data["merchants_count"] == 3

