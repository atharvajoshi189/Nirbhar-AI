import os
import sys
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vuhyryjnrlgueielndvz.supabase.co").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

USER_A_EMAIL = "user_a_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"

def test_task_creation_and_coordinator_run():
    print("=" * 70)
    print("NIRBHAR AI — PHASE 2 END-TO-END BACKEND VERIFICATION")
    print("=" * 70)

    # 1. Sign in User A
    print("\n[Step 1] Authenticating User A...")
    auth_res = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SERVICE_KEY, "Content-Type": "application/json"},
        json={"email": USER_A_EMAIL, "password": PASSWORD},
        timeout=10.0
    )
    assert auth_res.status_code == 200, f"Auth failed: {auth_res.text}"
    token_a = auth_res.json()["access_token"]
    user_id = auth_res.json()["user"]["id"]
    print(f"  Authenticated User A ID: {user_id}")

    # 2. Call POST /tasks
    print("\n[Step 2] Calling POST http://127.0.0.1:8000/tasks...")
    task_payload = {
        "title": "Cloud Infrastructure & Database Setup",
        "description": "Procure a production-grade PostgreSQL instance and CDN edge storage for a financial services microservice with strict high availability.",
        "budget_max": 250.00,
        "currency": "USD",
        "approval_mode": "above_limit",
        "auto_approve_threshold": 60.00,
        "single_tx_limit": 150.00,
        "allowed_domains": ["aws.amazon.com", "supabase.com", "cloudflare.com"],
        "blacklisted_domains": ["sketchy-hosting.cc", "unverified-vps.io"],
        "strict_mode": True
    }

    create_res = httpx.post(
        "http://127.0.0.1:8000/tasks",
        headers={"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"},
        json=task_payload,
        timeout=15.0
    )
    print(f"  Response Status: {create_res.status_code}")
    print(f"  Response JSON: {create_res.text}")
    assert create_res.status_code == 201, f"Failed: {create_res.text}"
    created_data = create_res.json()
    task_id = created_data["task"]["id"]
    print(f"  Created Task ID: {task_id}")
    print(f"  Audit Event Sequence: {created_data['audit_event']['sequence_number']}")
    print(f"  Audit Event Hash: {created_data['audit_event']['hash'][:20]}...")

    # 3. Wait for background coordinator agent to run via ARQ + Gemini
    print("\n[Step 3] Waiting for Coordinator Agent execution in ARQ...")
    completed = False
    for i in range(12):
        time.sleep(2)
        activity_res = httpx.get(
            f"http://127.0.0.1:8000/tasks/{task_id}/activity",
            headers={"Authorization": f"Bearer {token_a}"},
            timeout=10.0
        )
        runs = activity_res.json()
        print(f"  Poll {i+1}: {len(runs)} agent run(s) found.")
        if runs:
            latest = runs[-1]
            status = latest.get("status")
            print(f"    Latest Run Status: {status}, Model: {latest.get('model_name')}, Latency: {latest.get('latency_ms')}ms")
            if status == "COMPLETED":
                completed = True
                print("\n  [SUCCESS] Coordinator agent completed execution!")
                plan = latest.get("output_payload", {}).get("plan", {})
                print(f"    Summary: {plan.get('summary')}")
                print(f"    Total Planned Budget: ${plan.get('total_budget')}")
                print(f"    Subtasks ({len(plan.get('subtasks', []))}):")
                for st in plan.get("subtasks", []):
                    print(f"      - [{st.get('service_category')}] {st.get('title')}: ${st.get('allocated_budget')} (Vendor: {st.get('target_vendor_hint')})")
                print(f"    Tokens: {latest.get('prompt_tokens')} prompt, {latest.get('completion_tokens')} completion")
                print(f"    Signature: {latest.get('signature')[:24]}...")
                break
            elif status == "FAILED":
                raise RuntimeError(f"Coordinator agent run failed: {latest.get('output_payload')}")

    assert completed, "Coordinator agent run timed out"

    # 4. Check stats endpoint
    print("\n[Step 4] Checking GET http://127.0.0.1:8000/stats...")
    stats_res = httpx.get(
        "http://127.0.0.1:8000/stats",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=10.0
    )
    print(f"  Stats: {stats_res.json()}")
    assert stats_res.status_code == 200
    assert stats_res.json()["tasks_count"] >= 1

    print("\n[PASSED] All Phase 2 backend components verified successfully!")

if __name__ == "__main__":
    test_task_creation_and_coordinator_run()

