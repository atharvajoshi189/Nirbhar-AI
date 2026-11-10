import os
import sys
import json
import time
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

BASE_API = "http://127.0.0.1:8000"
GATEWAY_API = "http://127.0.0.1:8001"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASSWORD = "NirbharSecurePass2026!"

def run_phase4_test():
    print("=" * 80)
    print("NIRBHAR AI — PHASE 4 TRUST ENGINE INTEGRATION & HUMAN REVIEW TEST")
    print("=" * 80)

    # 1. Login
    print("\n[Step 1] Authenticating as User A...")
    from app.db.supabase import get_supabase_admin_client
    supabase = get_supabase_admin_client()
    auth_resp = supabase.auth.sign_in_with_password({"email": USER_EMAIL, "password": USER_PASSWORD})
    user_id = auth_resp.user.id
    access_token = auth_resp.session.access_token
    headers = {"Authorization": f"Bearer {access_token}"}
    print(f"  [PASSED] Authenticated User ID: {user_id}")

    # 2. Create Task with low auto_approve_threshold ($15.00)
    print("\n[Step 2] Creating Task with auto_approve_threshold = $15.00...")
    task_resp = httpx.post(
        f"{BASE_API}/tasks",
        headers=headers,
        json={
            "title": "Phase 4 Trust Engine Verification Task",
            "description": "Evaluate vendor procurement with deterministic Trust Engine and human approval review",
            "budget_max": 100.00,
            "currency": "USD",
            "auto_approve_threshold": 15.00,
            "single_tx_limit": 50.00
        },
        timeout=15.0
    )
    assert task_resp.status_code == 201, f"Task creation failed: {task_resp.text}"
    task_id = task_resp.json()["task"]["id"]
    print(f"  [PASSED] Created Task ID: {task_id}")

    # 3. Request Quote from Vendor Gateway ($18.00 > $15.00 threshold)
    print("\n[Step 3] Fetching dynamic quote from Vendor Gateway ($18.00)...")
    quote_resp = httpx.post(
        f"{GATEWAY_API}/quote",
        json={
            "task_id": task_id,
            "service_category": "competitor_analysis",
            "service_name": "Premium Competitor Intelligence Audit",
            "scope_details": "Comprehensive 50-page enterprise market positioning analysis",
            "tier": "standard",
            "units": 1
        },
        timeout=10.0
    )
    assert quote_resp.status_code == 201, f"Quote fetch failed: {quote_resp.text}"
    quote_data = quote_resp.json()
    print(f"  [PASSED] Quote ID: {quote_data['quote_id']} | Amount: ${quote_data['amount']:.2f}")

    # 4. Sign proposal with Service Agent Ed25519 key
    print("\n[Step 4] Signing proposal with Service Agent Ed25519 key...")
    from app.services.agents import ensure_user_agent
    from app.security.agent_keys import agent_key_manager
    agent_id = ensure_user_agent(user_id=user_id, role="service")

    proposal_dict = {
        "agent_id": agent_id,
        "task_id": task_id,
        "provider": quote_data["merchant_name"],
        "service": quote_data["service_name"],
        "amount": quote_data["amount"],
        "currency": quote_data["currency"],
        "quote_id": quote_data["quote_id"],
        "justification": f"Selected {quote_data['merchant_name']} for comprehensive competitor audit at competitive ${quote_data['amount']:.2f} rate.",
        "quote_details": quote_data
    }
    signature = agent_key_manager.sign_proposal(role="service", payload=proposal_dict)
    print(f"  [PASSED] Generated Ed25519 signature: {signature[:24]}...")

    # 5. Propose transaction through Trust Engine
    print("\n[Step 5] Submitting proposal to POST /transactions/propose...")
    propose_resp = httpx.post(
        f"{BASE_API}/transactions/propose",
        headers=headers,
        json={
            "proposal": proposal_dict,
            "signature": signature
        },
        timeout=15.0
    )
    assert propose_resp.status_code == 201, f"Proposal failed: {propose_resp.text}"
    propose_data = propose_resp.json()
    tx_id = propose_data["transaction"]["id"]
    trust_dec = propose_data["trust_decision"]
    decision = trust_dec["decision"]
    reason_codes = trust_dec["rules_evaluated"][-1].get("reason_codes", [])
    print(f"  [PASSED] Transaction ID: {tx_id}")
    print(f"  [PASSED] Trust Decision: {decision}")
    print(f"  [PASSED] Reason Codes: {reason_codes}")
    print(f"  [PASSED] Risk Score: {trust_dec['risk_score']}")
    assert decision == "NEEDS_HUMAN_APPROVAL", f"Expected NEEDS_HUMAN_APPROVAL, got {decision}"
    assert "USER_APPROVAL_REQUIRED" in reason_codes, "Expected USER_APPROVAL_REQUIRED reason code"

    # 6. Fetch Trust Review via GET /transactions/{tx_id}/trust-review
    print("\n[Step 6] Testing GET /transactions/{tx_id}/trust-review...")
    review_resp = httpx.get(
        f"{BASE_API}/transactions/{tx_id}/trust-review",
        headers=headers,
        timeout=10.0
    )
    assert review_resp.status_code == 200, f"Trust review endpoint failed: {review_resp.text}"
    review_data = review_resp.json()
    print(f"  [PASSED] Provider: {review_data['provider']}")
    print(f"  [PASSED] Amount: ${review_data['amount']:.2f}")
    print(f"  [PASSED] Budget Remaining: ${review_data['budget_remaining']:.2f}")
    print(f"  [PASSED] Checks count: {len(review_data['checks'])}")
    for c in review_data["checks"]:
        symbol = "✓" if c["passed"] else "✗"
        print(f"    [{symbol}] {c['check_name']}: {c['message']}")

    # 7. Approve Transaction via POST /transactions/{tx_id}/approve
    print("\n[Step 7] Testing POST /transactions/{tx_id}/approve (Human Approval)...")
    approve_resp = httpx.post(
        f"{BASE_API}/transactions/{tx_id}/approve",
        headers=headers,
        json={"notes": "Approved by verified human reviewer in Phase 4 test."},
        timeout=10.0
    )
    assert approve_resp.status_code == 200, f"Approval failed: {approve_resp.text}"
    approved_payload = approve_resp.json()
    print(f"  [PASSED] Approval response: {approved_payload}")
    assert approved_payload["status"] == "APPROVED"

    # Also verify transaction status updated in DB
    tx_check = httpx.get(f"{BASE_API}/transactions/{tx_id}", headers=headers, timeout=10.0)
    assert tx_check.status_code == 200
    assert tx_check.json()["status"] == "APPROVED"
    print(f"  [PASSED] Verified Transaction status in DB is APPROVED!")

    print("\n" + "=" * 80)
    print("ALL PHASE 4 INTEGRATION CHECKS PASSED!")
    print("=" * 80)
    return {
        "task_id": task_id,
        "transaction_id": tx_id,
        "trust_decision": trust_dec,
        "review_data": review_data
    }

if __name__ == "__main__":
    run_phase4_test()
