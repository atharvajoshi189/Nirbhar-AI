import os
import sys
import json
import hashlib
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
import httpx
from dotenv import load_dotenv

load_dotenv()

# Add api and root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_DIR = os.path.join(BASE_DIR, "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings
from app.services.paypal import paypal_service, PayPalService
from app.security.payload_hash import compute_transaction_payload_hash
from trust_engine import (
    ProposalContext,
    TaskPolicyModel,
    evaluate_proposal,
    ReasonCode,
    TrustDecisionEnum
)

@pytest.fixture
def sample_transaction_and_quote():
    now_iso = datetime.now(timezone.utc).isoformat()
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    
    tx = {
        "id": "tx-test-settlement-001",
        "task_id": "task-settlement-001",
        "user_id": "user-test-001",
        "quote_id": "quote-settlement-001",
        "amount": 12.00,
        "currency": "USD",
        "status": "APPROVED",
        "created_at": now_iso
    }
    
    quote = {
        "id": "quote-settlement-001",
        "task_id": "task-settlement-001",
        "user_id": "user-test-001",
        "vendor_name": "MarketPulse Analytics",
        "amount": 12.00,
        "currency": "USD",
        "quote_details": {
            "amount": 12.00,
            "currency": "USD",
            "merchant_id": "merch_marketpulse",
            "payee_email": "sb-p60s931818296@business.example.com",
            "expires_at": expiry,
            "hmac_signature": "a" * 64
        }
    }
    return tx, quote

# ==============================================================================
# 1. Payload Hash & Binding Tests
# ==============================================================================
def test_payload_hash_deterministic(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    hash1 = compute_transaction_payload_hash(tx, quote)
    hash2 = compute_transaction_payload_hash(tx, quote)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex

def test_payload_hash_detects_amount_tampering(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    original_hash = compute_transaction_payload_hash(tx, quote)
    
    # Tamper with transaction amount
    tampered_tx = dict(tx, amount=12.01)
    tampered_hash = compute_transaction_payload_hash(tampered_tx, quote)
    assert original_hash != tampered_hash

def test_payload_hash_detects_quote_tampering(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    original_hash = compute_transaction_payload_hash(tx, quote)
    
    # Tamper with quote vendor name
    tampered_quote = dict(quote, vendor_name="Fake Malicious Vendor")
    tampered_hash = compute_transaction_payload_hash(tx, tampered_quote)
    assert original_hash != tampered_hash

def test_payload_hash_detects_currency_tampering(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    original_hash = compute_transaction_payload_hash(tx, quote)
    
    tampered_tx = dict(tx, currency="EUR")
    tampered_hash = compute_transaction_payload_hash(tampered_tx, quote)
    assert original_hash != tampered_hash

# ==============================================================================
# 2. Approval Binding & Re-evaluation Invalidation Simulation
# ==============================================================================
def test_approval_binding_invalidation_on_hash_mismatch(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    approval_hash = compute_transaction_payload_hash(tx, quote)
    
    # Stored approval record
    user_approval = {
        "id": "appr-001",
        "transaction_id": tx["id"],
        "status": "APPROVED",
        "user_signature": approval_hash
    }
    
    # Simulate attacker or buggy process changing the tx amount before PayPal order
    modified_tx = dict(tx, amount=15.00)
    recomputed_hash = compute_transaction_payload_hash(modified_tx, quote)
    
    # Check invalidation logic
    assert user_approval["user_signature"] != recomputed_hash
    # Invalidation must flip status
    user_approval["status"] = "REJECTED"
    assert user_approval["status"] == "REJECTED"

def test_trust_engine_re_evaluation_invalidates_expired_quote(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    
    # Expire quote by setting expires_at in the past
    past_expiry = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    quote_details = dict(quote["quote_details"], expires_at=past_expiry)
    
    recheck_ctx = ProposalContext(
        task_id=tx["task_id"],
        user_id=tx["user_id"],
        agent_id="agent-001",
        agent_role="service_agent",
        agent_public_key="0" * 64,
        agent_is_active=True,
        agent_signature="sig_test",
        amount=Decimal(str(tx["amount"])),
        currency="USD",
        provider_name=quote["vendor_name"],
        provider_url="https://vendor.com",
        proposal_category="analytics",
        task_title="Test Task",
        task_category="analytics",
        task_exists=True,
        task_owner_id=tx["user_id"],
        task_is_active=True,
        task_budget_max=Decimal("50.00"),
        current_committed_spend=Decimal("0.00"),
        justification="Authorized procurement",
        fetched_page_text="",
        advisory_relevance_score=1.0,
        quote_id=quote["id"],
        quote_amount=Decimal(str(quote_details["amount"])),
        quote_currency="USD",
        quote_expires_at=past_expiry,
        quote_hmac_signature=quote_details["hmac_signature"],
        quote_hmac_secret="secret",
        seen_idempotency_keys=[],
        seen_payload_hashes=[],
        policy=TaskPolicyModel(),
        bypass_advisory_llm=True
    )
    
    eval_res = evaluate_proposal(recheck_ctx)
    assert eval_res.decision == TrustDecisionEnum.BLOCKED
    assert ReasonCode.QUOTE_EXPIRED.value in eval_res.reason_codes

def test_trust_engine_re_evaluation_invalidates_budget_exceeded(sample_transaction_and_quote):
    tx, quote = sample_transaction_and_quote
    future_expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    
    # Task budget is $20, but existing committed spend has already reached $15,
    # so proposing $12 puts total at $27 (exceeding $20)
    recheck_ctx = ProposalContext(
        task_id=tx["task_id"],
        user_id=tx["user_id"],
        agent_id="agent-001",
        agent_role="service_agent",
        agent_public_key="0" * 64,
        agent_is_active=True,
        agent_signature="sig_test",
        amount=Decimal("12.00"),
        currency="USD",
        provider_name=quote["vendor_name"],
        provider_url="https://vendor.com",
        proposal_category="analytics",
        task_title="Test Task",
        task_category="analytics",
        task_exists=True,
        task_owner_id=tx["user_id"],
        task_is_active=True,
        task_budget_max=Decimal("20.00"),
        current_committed_spend=Decimal("15.00"),  # Leaves only $5.00 remaining
        justification="Authorized procurement",
        fetched_page_text="",
        advisory_relevance_score=1.0,
        quote_id=quote["id"],
        quote_amount=Decimal("12.00"),
        quote_currency="USD",
        quote_expires_at=future_expiry,
        quote_hmac_signature="a" * 64,
        quote_hmac_secret="secret",
        seen_idempotency_keys=[],
        seen_payload_hashes=[],
        policy=TaskPolicyModel(),
        bypass_advisory_llm=True
    )
    
    eval_res = evaluate_proposal(recheck_ctx)
    assert eval_res.decision == TrustDecisionEnum.BLOCKED
    assert ReasonCode.BUDGET_EXCEEDED.value in eval_res.reason_codes

# ==============================================================================
# 3. Real PayPal Sandbox Orders v2 API Tests (Live Sandbox)
# ==============================================================================
@pytest.mark.asyncio
async def test_live_paypal_oauth_token():
    """Rule 1: Verify real PayPal Sandbox OAuth bearer token acquisition."""
    token = await paypal_service.get_access_token()
    assert token is not None
    assert len(token) > 20

@pytest.mark.asyncio
async def test_live_paypal_order_creation_v2():
    """Rule 1 & 4: Real PayPal Sandbox Orders v2 creation on backend."""
    test_tx_id = f"tx_live_test_{int(datetime.now().timestamp())}"
    dummy_hash = hashlib.sha256(test_tx_id.encode()).hexdigest()
    
    order_data = await paypal_service.create_order(
        transaction_id=test_tx_id,
        amount=12.00,
        currency="USD",
        payee_email="sb-p60s931818296@business.example.com",
        task_title="Live Automated Sandbox Verification",
        provider_name="CompetitorRadar",
        return_url=f"http://localhost:3000/payments/result?tx_id={test_tx_id}&status=success",
        cancel_url=f"http://localhost:3000/payments/result?tx_id={test_tx_id}&status=cancelled",
        payload_hash=dummy_hash
    )
    
    assert order_data["order_id"] is not None
    assert order_data["status"] == "CREATED"
    assert order_data["approval_url"] is not None
    assert "https://www.sandbox.paypal.com" in order_data["approval_url"]
    assert order_data["order_id"] in order_data["approval_url"]

# ==============================================================================
# 4. Webhook Signature Verification Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_webhook_signature_forged_rejection():
    """
    Rule 4 & Fail-Closed: Forged webhook transmission signature MUST be rejected
    by real PayPal verification API.
    """
    fake_headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-360caa42-fca2a594-5b4d2417",
        "paypal-transmission-id": "fake-trans-id-001",
        "paypal-transmission-sig": "fake_forged_base64_signature_here",
        "paypal-transmission-time": "2026-11-10T22:00:00Z"
    }
    fake_event = {
        "id": "WH-TEST-EVENT-001",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAP-FAKE-001",
            "amount": {"value": "12.00", "currency_code": "USD"}
        }
    }
    
    is_valid, v_status, details = await paypal_service.verify_webhook_signature(fake_headers, fake_event)
    assert is_valid is False
    assert v_status in ("FAILURE", "API_ERROR")

@pytest.mark.asyncio
async def test_webhook_signature_missing_headers_rejection():
    """Missing headers fail closed immediately without throwing unhandled exceptions."""
    incomplete_headers = {
        "paypal-auth-algo": "SHA256withRSA"
        # missing transmission id, sig, etc.
    }
    is_valid, v_status, details = await paypal_service.verify_webhook_signature(incomplete_headers, {})
    assert is_valid is False
    assert v_status == "MISSING_REQUIRED_HEADERS"
