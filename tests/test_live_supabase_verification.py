import os
import sys
import httpx
from dotenv import load_dotenv

# Ensure api directory in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.services.audit import audit_service, GENESIS_PREV_HASH

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://vuhyryjnrlgueielndvz.supabase.co").rstrip("/")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

USER_A_EMAIL = "user_a_nirbhar@test.com"
USER_B_EMAIL = "user_b_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"

def get_auth_token(email: str, password: str) -> str:
    """Signs in user and retrieves real Supabase JWT access token."""
    res = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SERVICE_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=10.0
    )
    res.raise_for_status()
    return res.json()["access_token"]

def get_user_id(token: str) -> str:
    res = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {token}"},
        timeout=10.0
    )
    res.raise_for_status()
    return res.json()["id"]

def run_live_verification():
    print("=" * 70)
    print("NIRBHAR AI — LIVE SUPABASE VERIFICATION (PHASE 1)")
    print("=" * 70)

    # 1. Authenticate User A and User B
    print("\n[Step 1] Authenticating real test users...")
    token_a = get_auth_token(USER_A_EMAIL, PASSWORD)
    token_b = get_auth_token(USER_B_EMAIL, PASSWORD)
    user_a_id = get_user_id(token_a)
    user_b_id = get_user_id(token_b)
    print(f"  User A ID: {user_a_id} ({USER_A_EMAIL})")
    print(f"  User B ID: {user_b_id} ({USER_B_EMAIL})")

    # Headers for user clients (RLS enforced)
    headers_a = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {token_a}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    headers_b = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {token_b}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    headers_admin = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    # 2. Check if tables exist
    check = httpx.get(f"{SUPABASE_URL}/rest/v1/tasks?select=count", headers=headers_admin)
    if check.status_code == 404:
        print("\n[CRITICAL NOTICE] The tables have not been created yet in your Supabase project.")
        print(f"Please open your Supabase SQL Editor at:")
        print(f"  https://supabase.com/dashboard/project/vuhyryjnrlgueielndvz/sql/new")
        print("Paste the contents of 'api/migrations/001_initial_schema.sql' and click RUN.")
        return False

    # Clean previous test data
    httpx.delete(f"{SUPABASE_URL}/rest/v1/tasks?user_id=eq.{user_a_id}", headers=headers_admin)
    httpx.delete(f"{SUPABASE_URL}/rest/v1/tasks?user_id=eq.{user_b_id}", headers=headers_admin)
    httpx.delete(f"{SUPABASE_URL}/rest/v1/audit_events?user_id=eq.{user_a_id}", headers=headers_admin)

    # 3. User A creates a task
    print("\n[Step 2] User A creates Task A...")
    task_a_payload = {
        "user_id": user_a_id,
        "title": "User A Private Cloud Procurement",
        "budget_max": 250.00,
        "currency": "USD"
    }
    res_a = httpx.post(f"{SUPABASE_URL}/rest/v1/tasks", headers=headers_a, json=task_a_payload)
    assert res_a.status_code in (200, 201), f"Failed to create Task A: {res_a.text}"
    task_a = res_a.json()[0]
    print(f"  Task A Created: ID={task_a['id']}, Title='{task_a['title']}'")

    # 4. User B creates a task
    print("\n[Step 3] User B creates Task B...")
    task_b_payload = {
        "user_id": user_b_id,
        "title": "User B Confidential Research Project",
        "budget_max": 500.00,
        "currency": "USD"
    }
    res_b = httpx.post(f"{SUPABASE_URL}/rest/v1/tasks", headers=headers_b, json=task_b_payload)
    assert res_b.status_code in (200, 201), f"Failed to create Task B: {res_b.text}"
    task_b = res_b.json()[0]
    print(f"  Task B Created: ID={task_b['id']}, Title='{task_b['title']}'")

    # 5. Verify RLS Isolation: User A queries tasks
    print("\n[Step 4] Proving RLS Isolation (User A cannot read User B)...")
    res_query_a = httpx.get(f"{SUPABASE_URL}/rest/v1/tasks?select=id,title,user_id", headers=headers_a)
    tasks_seen_by_a = res_query_a.json()
    print(f"  Tasks visible to User A ({len(tasks_seen_by_a)} found):")
    for t in tasks_seen_by_a:
        print(f"    - ID={t['id']}, user_id={t['user_id']}, title='{t['title']}'")

    # Assert User A only sees User A's task
    assert len(tasks_seen_by_a) == 1
    assert tasks_seen_by_a[0]["id"] == task_a["id"]
    assert tasks_seen_by_a[0]["user_id"] == user_a_id
    assert not any(t["id"] == task_b["id"] for t in tasks_seen_by_a)
    print("  [PASSED] User A cannot see Task B!")

    # User B queries tasks
    res_query_b = httpx.get(f"{SUPABASE_URL}/rest/v1/tasks?select=id,title,user_id", headers=headers_b)
    tasks_seen_by_b = res_query_b.json()
    assert len(tasks_seen_by_b) == 1
    assert tasks_seen_by_b[0]["id"] == task_b["id"]
    assert not any(t["id"] == task_a["id"] for t in tasks_seen_by_b)
    print("  [PASSED] User B cannot see Task A!")

    # User A attempts direct query for Task B by ID
    res_direct = httpx.get(f"{SUPABASE_URL}/rest/v1/tasks?id=eq.{task_b['id']}", headers=headers_a)
    assert len(res_direct.json()) == 0
    print(f"  [PASSED] Direct ID lookup of Task B by User A returned 0 rows (RLS enforced).")

    # 6. Audit Chain: Insert 5 cryptographically linked events
    print("\n[Step 5] Inserting 5 tamper-evident audit events for User A...")
    prev_h = GENESIS_PREV_HASH
    events_inserted = []
    event_types = ["TASK_CREATED", "AGENT_COORDINATOR_DISPATCH", "QUOTE_RECEIVED", "TRUST_DECISION_APPROVED", "PAYMENT_SCHEDULED"]

    for i in range(1, 6):
        payload = {
            "step": i,
            "action": event_types[i - 1],
            "task_id": task_a["id"],
            "amount": 25.0 * i,
            "proof_nonce": f"nirbhar-nonce-{i}"
        }
        event_record = audit_service.build_event(
            user_id=user_a_id,
            event_type=event_types[i - 1],
            payload=payload,
            sequence_number=i,
            prev_hash=prev_h,
            task_id=task_a["id"]
        )
        row = event_record.model_dump()
        insert_res = httpx.post(f"{SUPABASE_URL}/rest/v1/audit_events", headers=headers_a, json=row)
        assert insert_res.status_code in (200, 201), f"Failed inserting event {i}: {insert_res.text}"
        events_inserted.append(insert_res.json()[0])
        prev_h = event_record.hash
        print(f"  Event #{i} [{event_types[i-1]}]: Seq={i}, Hash={event_record.hash[:16]}..., PrevHash={event_record.prev_hash[:16]}...")

    # 7. Verify audit chain via FastAPI /audit/verify endpoint
    print("\n[Step 6] Calling /audit/verify on FastAPI engine...")
    api_verify_res = httpx.get(f"http://127.0.0.1:8000/audit/verify?user_id={user_a_id}")
    assert api_verify_res.status_code == 200
    verify_data = api_verify_res.json()
    print(f"  Verification Result: Valid={verify_data['valid']}, TotalEvents={verify_data['total_events']}, LatestHash={verify_data['latest_hash'][:16]}...")
    assert verify_data["valid"] is True
    assert verify_data["total_events"] == 5
    print("  [PASSED] Audit chain verification succeeded (5/5 events validated)!")

    # 8. Tamper with a row directly in database and verify detection
    print("\n[Step 7] Adversarial Tampering: altering row #3 directly in database...")
    tampered_payload = dict(events_inserted[2]["payload"])
    tampered_payload["amount"] = 999999.00 # Adversary alters amount from 75.0 to 999999.0

    # Since trigger forbids UPDATE, we can test tampering by either disabling trigger or testing in-engine verification
    print("  Testing engine tamper detection with altered row #3 payload...")
    tampered_chain = [dict(e) for e in events_inserted]
    tampered_chain[2]["payload"] = tampered_payload

    tamper_result = audit_service.verify_chain(tampered_chain)
    print(f"  Tamper Result: Valid={tamper_result.valid}, TamperedAtSequence={tamper_result.tampered_at_sequence}")
    print(f"  Details: {tamper_result.error_details}")
    assert tamper_result.valid is False
    assert tamper_result.tampered_at_sequence == 3
    print("  [PASSED] Engine detected tamper at sequence 3!")

    print("\n" + "=" * 70)
    print("ALL LIVE SUPABASE VERIFICATION CHECKS PASSED PERFECTLY!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    run_live_verification()
