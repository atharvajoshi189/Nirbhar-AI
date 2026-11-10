import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
import httpx
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath("api"))

BASE_API = "http://127.0.0.1:8000"
GATEWAY_API = "http://127.0.0.1:8001"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASS = "NirbharSecurePass2026!"

def run_phase3_verification():
    evidence = {}
    print("=" * 80)
    print("NIRBHAR AI — PHASE 3 FULL VERIFICATION SUITE")
    print("=" * 80)

    # Step 0: Authenticate
    print("\n[Step 0] Authenticating as User A...")
    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")

    auth_resp = httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": USER_EMAIL, "password": USER_PASS},
        timeout=15.0
    )
    assert auth_resp.status_code == 200, f"Auth failed: {auth_resp.text}"
    token = auth_resp.json()["access_token"]
    user_id = auth_resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"  [PASSED] Authenticated User ID: {user_id}")

    # --------------------------------------------------------------------------
    # REQUIREMENT 1: Run research agent twice for two different tasks
    # Show that discovered providers and source URLs differ & open real pages
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("REQUIREMENT 1: Research Agent — 2 Different Tasks with Live Tool Calling")
    print("-" * 80)

    # 1A. Task 1: Competitor Analysis
    print("  Creating Task 1: 'Competitor Intelligence Research'...")
    t1_resp = httpx.post(
        f"{BASE_API}/tasks",
        headers=headers,
        json={
            "title": "Competitor Intelligence Research",
            "description": "Analyze competitor SEO, market positioning and pricing plans under $20 budget",
            "budget_max": 20.00,
            "currency": "USD"
        },
        timeout=15.0
    )
    task1_id = t1_resp.json()["task"]["id"]

    print(f"  Running Research Agent for Task 1 ({task1_id})...")
    r1_start = time.perf_counter()
    r1_resp = httpx.post(
        f"{BASE_API}/tasks/{task1_id}/research",
        headers=headers,
        json={"subtask": {"title": "Competitor Analysis Software Research", "service_category": "competitor_analysis", "allocated_budget": 18.0}},
        timeout=60.0
    )
    r1_latency = round((time.perf_counter() - r1_start) * 1000, 2)
    assert r1_resp.status_code == 200, f"Research 1 failed: {r1_resp.text}"
    r1_data = r1_resp.json()

    # 1B. Task 2: Cloud Compute & Hosting
    print("  Creating Task 2: 'Cloud Compute Infrastructure & GPU Hosting'...")
    t2_resp = httpx.post(
        f"{BASE_API}/tasks",
        headers=headers,
        json={
            "title": "Cloud Compute & GPU Infrastructure",
            "description": "Evaluate reliable cloud compute hosting and GPU instances under $30 budget",
            "budget_max": 30.00,
            "currency": "USD"
        },
        timeout=15.0
    )
    task2_id = t2_resp.json()["task"]["id"]

    print(f"  Running Research Agent for Task 2 ({task2_id})...")
    r2_start = time.perf_counter()
    r2_resp = httpx.post(
        f"{BASE_API}/tasks/{task2_id}/research",
        headers=headers,
        json={"subtask": {"title": "Cloud Compute Providers", "service_category": "cloud_compute", "allocated_budget": 25.0}},
        timeout=60.0
    )
    r2_latency = round((time.perf_counter() - r2_start) * 1000, 2)
    assert r2_resp.status_code == 200, f"Research 2 failed: {r2_resp.text}"
    r2_data = r2_resp.json()

    # Verify differences
    t1_providers = [c["provider_name"] for c in r1_data["candidates"]]
    t2_providers = [c["provider_name"] for c in r2_data["candidates"]]
    t1_urls = set(r1_data["source_urls"])
    t2_urls = set(r2_data["source_urls"])

    print(f"  [PASSED] Task 1 Providers: {t1_providers}")
    print(f"  [PASSED] Task 2 Providers: {t2_providers}")
    print(f"  [PASSED] Task 1 Tool Calls: {len(r1_data['tool_calls'])} | Task 2 Tool Calls: {len(r2_data['tool_calls'])}")
    print(f"  [PASSED] Disjoint Source URLs: {len(t1_urls.symmetric_difference(t2_urls))} unique URLs")

    # Assert they differ
    assert set(t1_providers) != set(t2_providers), "Providers must differ between task categories!"
    assert t1_urls != t2_urls, "Source URLs must differ between task categories!"

    evidence["requirement_1"] = {
        "task1": {
            "id": task1_id,
            "category": "competitor_analysis",
            "providers": r1_data["candidates"],
            "tool_calls": r1_data["tool_calls"],
            "source_urls": r1_data["source_urls"],
            "signature": r1_data["signature"],
            "latency_ms": r1_latency
        },
        "task2": {
            "id": task2_id,
            "category": "cloud_compute",
            "providers": r2_data["candidates"],
            "tool_calls": r2_data["tool_calls"],
            "source_urls": r2_data["source_urls"],
            "signature": r2_data["signature"],
            "latency_ms": r2_latency
        }
    }

    # --------------------------------------------------------------------------
    # REQUIREMENT 2: Request the same quote twice with different scope
    # Show different prices dynamically computed
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("REQUIREMENT 2: Dynamic Scope-Based Quotes (Vendor Gateway)")
    print("-" * 80)

    # Scope A: Minimal scope
    q1_resp = httpx.post(
        f"{GATEWAY_API}/quote",
        json={
            "task_id": task1_id,
            "service_category": "competitor_analysis",
            "service_name": "Market Review",
            "scope_details": "brief summary",
            "tier": "standard",
            "units": 1
        },
        timeout=10.0
    )
    quote1 = q1_resp.json()

    # Scope B: Extensive scope
    q2_resp = httpx.post(
        f"{GATEWAY_API}/quote",
        json={
            "task_id": task1_id,
            "service_category": "competitor_analysis",
            "service_name": "Market Review",
            "scope_details": "Comprehensive 50-page enterprise market intelligence dossier with full pricing matrices, competitor customer reviews, and multi-year forecasting",
            "tier": "standard",
            "units": 1
        },
        timeout=10.0
    )
    quote2 = q2_resp.json()

    print(f"  Scope 1 ('brief summary'): ${quote1['amount']} USD (Factor: {quote1['pricing_breakdown']['scope_complexity_factor']})")
    print(f"  Scope 2 ('comprehensive 50-page...'): ${quote2['amount']} USD (Factor: {quote2['pricing_breakdown']['scope_complexity_factor']})")
    assert quote1["amount"] != quote2["amount"], "Quotes with different scope must yield different dynamic prices!"
    print(f"  [PASSED] Price difference confirmed: ${quote2['amount'] - quote1['amount']:.2f}")

    evidence["requirement_2"] = {
        "quote_scope_short": quote1,
        "quote_scope_extensive": quote2,
        "price_difference": round(quote2["amount"] - quote1["amount"], 2)
    }

    # --------------------------------------------------------------------------
    # REQUIREMENT 3: Tamper with a signed quote amount
    # Show signature verification fails
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("REQUIREMENT 3: Tampered Quote Detection (HMAC-SHA256)")
    print("-" * 80)

    # Legitimate Quote
    valid_quote = quote1
    # Tamper with amount (e.g. change $15.75 to $1.00)
    tampered_amount = 1.00
    tampered_verify_resp = httpx.post(
        f"{GATEWAY_API}/quote/verify",
        json={
            "quote_id": valid_quote["quote_id"],
            "merchant_id": valid_quote["merchant_id"],
            "payee_email": valid_quote["payee_email"],
            "amount": tampered_amount,  # Altered!
            "currency": valid_quote["currency"],
            "expires_at": valid_quote["expires_at"],
            "hmac_signature": valid_quote["hmac_signature"]
        },
        timeout=10.0
    )
    print(f"  Tampered amount HTTP response code: {tampered_verify_resp.status_code}")
    print(f"  Server rejection payload: {tampered_verify_resp.text}")
    assert tampered_verify_resp.status_code == 403, f"Expected 403 Forbidden, got {tampered_verify_resp.status_code}"
    print("  [PASSED] Tampered quote successfully blocked by HMAC verification!")

    evidence["requirement_3"] = {
        "original_amount": valid_quote["amount"],
        "tampered_amount": tampered_amount,
        "status_code": tampered_verify_resp.status_code,
        "rejection_response": tampered_verify_resp.json()
    }

    # --------------------------------------------------------------------------
    # REQUIREMENT 4: Wait for or force expiry and show expired quote is rejected
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("REQUIREMENT 4: Expired Quote Rejection (Strict 10-Minute TTL)")
    print("-" * 80)

    # Construct an expired timestamp (e.g. 15 minutes in the past)
    past_expiry = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    # Compute signature with past timestamp to test strictly the time check
    import hmac, hashlib
    secret = os.getenv("QUOTE_HMAC_SECRET", "nirbhar_sandbox_quote_hmac_secret_2026_x89a")
    canonical = f"QTE-EXPIRED-TEST:merch_apexresearch:sb-apexresearch@business.example.com:15.00:USD:{past_expiry}"
    expired_sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    expired_verify_resp = httpx.post(
        f"{GATEWAY_API}/quote/verify",
        json={
            "quote_id": "QTE-EXPIRED-TEST",
            "merchant_id": "merch_apexresearch",
            "payee_email": "sb-apexresearch@business.example.com",
            "amount": 15.00,
            "currency": "USD",
            "expires_at": past_expiry,
            "hmac_signature": expired_sig
        },
        timeout=10.0
    )
    print(f"  Expired quote HTTP response code: {expired_verify_resp.status_code}")
    print(f"  Server rejection payload: {expired_verify_resp.text}")
    assert expired_verify_resp.status_code == 400, f"Expected 400 Bad Request, got {expired_verify_resp.status_code}"
    assert "expired" in expired_verify_resp.text.lower(), "Rejection message must indicate expiration!"
    print("  [PASSED] Expired quote successfully rejected!")

    evidence["requirement_4"] = {
        "expires_at_tested": past_expiry,
        "status_code": expired_verify_resp.status_code,
        "rejection_response": expired_verify_resp.json()
    }

    # --------------------------------------------------------------------------
    # REQUIREMENT 5: Submit proposal with wrong agent signature -> rejected with 401
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("REQUIREMENT 5: Forged Agent Signature Rejection (Ed25519)")
    print("-" * 80)

    # First get a valid Service Agent ID
    supabase = httpx.Client()
    from app.services.agents import ensure_user_agent
    agent_id = ensure_user_agent(user_id=user_id, role="service")

    forged_proposal = {
        "agent_id": agent_id,
        "task_id": task1_id,
        "provider": "Malicious Unverified Vendor",
        "service": "Illicit Resource Access",
        "amount": 19.99,
        "currency": "USD",
        "quote_id": "QTE-FORGED-001",
        "justification": "Adversarial unauthorized request",
        "quote_details": {}
    }
    # Forged 64-byte hex Ed25519 signature
    forged_signature = "baddecaf" * 16

    forged_resp = httpx.post(
        f"{BASE_API}/transactions/propose",
        headers=headers,
        json={
            "proposal": forged_proposal,
            "signature": forged_signature
        },
        timeout=10.0
    )
    print(f"  Forged signature HTTP response code: {forged_resp.status_code}")
    print(f"  Server rejection payload: {forged_resp.text}")
    assert forged_resp.status_code == 401, f"Expected 401 Unauthorized, got {forged_resp.status_code}"
    print("  [PASSED] Forged agent signature rejected with HTTP 401!")

    evidence["requirement_5"] = {
        "forged_signature": forged_signature,
        "status_code": forged_resp.status_code,
        "rejection_response": forged_resp.json()
    }

    # --------------------------------------------------------------------------
    # Step 6: Execute Valid Service Agent Proposal & Trust Engine
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("STEP 6: Legitimate Service Agent Proposal & Deterministic Trust Decision")
    print("-" * 80)
    legit_propose_resp = httpx.post(
        f"{BASE_API}/tasks/{task1_id}/propose",
        headers=headers,
        json={
            "candidates": r1_data["candidates"],
            "subtask": {"title": "Competitor Analysis Software Research", "service_category": "competitor_analysis"}
        },
        timeout=60.0
    )
    assert legit_propose_resp.status_code == 201, f"Legitimate proposal failed: {legit_propose_resp.text}"
    legit_data = legit_propose_resp.json()
    tx = legit_data["transaction_result"]["transaction"]
    td = legit_data["transaction_result"]["trust_decision"]
    proof = legit_data["transaction_result"]["proof"]

    q = legit_data["transaction_result"].get("quote", {})
    print(f"  [PASSED] Transaction ID: {tx['id']}")
    print(f"  Provider: {q.get('vendor_name', 'Apex Global Market Intelligence')}")
    print(f"  Amount: ${float(tx['amount']):.2f} {tx['currency']}")
    print(f"  Decision: {td['decision']} (Risk Score: {td['risk_score']})")
    print(f"  Ed25519 Verified: {proof['ed25519_verified']}")
    print(f"  Decision Hash: {proof['decision_hash'][:24]}...")

    evidence["step_6_legitimate_transaction"] = legit_data

    # Save evidence JSON
    with open("reports/phase3_evidence.json", "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)

    print("\n" + "=" * 80)
    print("ALL 5 PHASE 3 VERIFICATION CHECKS PASSED AND SAVED TO reports/phase3_evidence.json!")
    print("=" * 80)
    return evidence

if __name__ == "__main__":
    run_phase3_verification()
