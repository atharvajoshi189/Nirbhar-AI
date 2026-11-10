import os
import sys
import json
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_API = "http://127.0.0.1:8000"
GATEWAY_API = "http://127.0.0.1:8001"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASS = "NirbharSecurePass2026!"

def test_phase3_pipeline():
    print("=" * 80)
    print("NIRBHAR AI — PHASE 3 END-TO-END PIPELINE VERIFICATION")
    print("=" * 80)

    # 1. Sign in to get JWT token
    print("\n[Step 1] Authenticating as User A...")
    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")

    auth_resp = httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": USER_EMAIL, "password": USER_PASS},
        timeout=15.0
    )
    assert auth_resp.status_code == 200, f"Auth failed: {auth_resp.text}"
    auth_data = auth_resp.json()
    token = auth_data["access_token"]
    user_id = auth_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"  [PASSED] Authenticated! User ID: {user_id}")

    # 2. Verify Vendor Gateway Quote Generation & HMAC Signature
    print("\n[Step 2] Testing Vendor Gateway Dynamic Quotes & HMAC Signing...")
    quote_payload = {
        "task_id": "test-task-phase3",
        "service_category": "competitor_analysis",
        "service_name": "Deep Market Intelligence Dossier",
        "scope_details": "Comprehensive feature matrices, pricing plans, and sentiment analysis for top 3 competitors",
        "tier": "standard",
        "units": 1
    }
    q_resp = httpx.post(f"{GATEWAY_API}/quote", json=quote_payload, timeout=10.0)
    assert q_resp.status_code == 201, f"Quote failed: {q_resp.text}"
    quote = q_resp.json()
    print(f"  [PASSED] Quote generated: {quote['quote_id']}")
    print(f"  Merchant: {quote['merchant_name']} ({quote['merchant_id']})")
    print(f"  Payee: {quote['payee_email']}")
    print(f"  Amount: ${quote['amount']:.2f} {quote['currency']}")
    print(f"  Expires: {quote['expires_at']}")
    print(f"  HMAC: {quote['hmac_signature'][:24]}...")

    # Verify Quote
    v_resp = httpx.post(
        f"{GATEWAY_API}/quote/verify",
        json={
            "quote_id": quote["quote_id"],
            "merchant_id": quote["merchant_id"],
            "payee_email": quote["payee_email"],
            "amount": quote["amount"],
            "currency": quote["currency"],
            "expires_at": quote["expires_at"],
            "hmac_signature": quote["hmac_signature"]
        },
        timeout=10.0
    )
    assert v_resp.status_code == 200, f"Quote verification failed: {v_resp.text}"
    print("  [PASSED] HMAC Quote verified successfully!")

    # 3. Create or Fetch an active task for research
    print("\n[Step 3] Creating a task for research & procurement...")
    task_payload = {
        "title": "Phase 3 Competitor Intelligence & Benchmarking",
        "description": "Analyze market alternatives and procure competitor research dataset under $25 budget ceiling",
        "budget_max": 25.00,
        "currency": "USD",
        "approval_mode": "above_limit",
        "auto_approve_threshold": 20.00,
        "strict_mode": True
    }
    task_resp = httpx.post(f"{BASE_API}/tasks", headers=headers, json=task_payload, timeout=15.0)
    assert task_resp.status_code == 201, f"Task creation failed: {task_resp.text}"
    created_task = task_resp.json()["task"]
    task_id = created_task["id"]
    print(f"  [PASSED] Created Task ID: {task_id}")

    # 4. Trigger Research Agent (Real Gemini Function Calling with web_search + fetch_page)
    print("\n[Step 4] Executing Research Agent (Gemini Function Calling with Tavily & Fetch Page)...")
    res_start = time.perf_counter()
    research_resp = httpx.post(
        f"{BASE_API}/tasks/{task_id}/research",
        headers=headers,
        json={"subtask": {"title": "Competitor Analysis Software Research", "service_category": "competitor_analysis", "allocated_budget": 20.0}},
        timeout=60.0
    )
    res_latency = round((time.perf_counter() - res_start) * 1000, 2)
    assert research_resp.status_code == 200, f"Research failed: {research_resp.text}"
    research_data = research_resp.json()

    candidates = research_data.get("candidates", [])
    tool_calls = research_data.get("tool_calls", [])
    source_urls = research_data.get("source_urls", [])

    print(f"  [PASSED] Research completed in {res_latency}ms!")
    print(f"  Discovered Candidates: {len(candidates)}")
    for c in candidates:
        print(f"    - Provider: {c.get('provider_name')} | URL: {c.get('url')}")
    print(f"  Tool Calls Logged: {len(tool_calls)}")
    for tc in tool_calls:
        print(f"    - Tool: {tc.get('tool')} | Args: {tc.get('args')}")
    print(f"  Unique Source URLs: {len(source_urls)}")
    print(f"  Ed25519 Signature: {research_data.get('signature')[:24]}...")

    # 5. Trigger Service Agent & Transaction Propose
    print("\n[Step 5] Executing Service Agent (Evaluation, Ed25519 Proposal & Trust Engine)...")
    propose_start = time.perf_counter()
    propose_resp = httpx.post(
        f"{BASE_API}/tasks/{task_id}/propose",
        headers=headers,
        json={
            "candidates": candidates,
            "subtask": {"title": "Competitor Analysis Service", "service_category": "competitor_analysis"}
        },
        timeout=60.0
    )
    propose_latency = round((time.perf_counter() - propose_start) * 1000, 2)
    assert propose_resp.status_code == 201, f"Proposal failed: {propose_resp.text}"
    prop_data = propose_resp.json()

    tx = prop_data["transaction_result"]["transaction"]
    decision = prop_data["transaction_result"]["trust_decision"]
    proof = prop_data["transaction_result"]["proof"]

    print(f"  [PASSED] Transaction proposed in {propose_latency}ms!")
    print(f"  Transaction ID: {tx['id']}")
    print(f"  Amount: ${float(tx['amount']):.2f} {tx['currency']}")
    print(f"  Trust Engine Decision: {decision['decision']}")
    print(f"  Risk Score: {decision['risk_score']}")
    print(f"  Ed25519 Verified: {proof['ed25519_verified']}")
    print(f"  Quote HMAC Verified: {proof['hmac_verified']}")
    print(f"  Decision Hash: {proof['decision_hash'][:24]}...")

    print("\n" + "=" * 80)
    print("ALL PHASE 3 BACKEND PIPELINE REQUIREMENTS VERIFIED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    test_phase3_pipeline()
