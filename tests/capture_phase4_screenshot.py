import os
import sys
import time
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

BASE_API = "http://127.0.0.1:8000"
GATEWAY_API = "http://127.0.0.1:8001"
WEB_URL = "http://localhost:3000"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASSWORD = "NirbharSecurePass2026!"

def capture_phase4():
    print("Preparing Task and Proposal with NEEDS_HUMAN_APPROVAL for UI screenshot...")
    from app.db.supabase import get_supabase_admin_client
    supabase = get_supabase_admin_client()
    auth_resp = supabase.auth.sign_in_with_password({"email": USER_EMAIL, "password": USER_PASSWORD})
    user_id = auth_resp.user.id
    access_token = auth_resp.session.access_token
    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Create Task
    task_resp = httpx.post(
        f"{BASE_API}/tasks",
        headers=headers,
        json={
            "title": "Phase 4 Trust Review UI Demonstration",
            "description": "Procure specialized competitor benchmark intelligence report under strict policy review",
            "budget_max": 80.00,
            "currency": "USD",
            "auto_approve_threshold": 12.00,
            "single_tx_limit": 40.00
        },
        timeout=15.0
    )
    task_id = task_resp.json()["task"]["id"]

    # 2. Get Quote ($16.50 > $12.00)
    quote_resp = httpx.post(
        f"{GATEWAY_API}/quote",
        json={
            "task_id": task_id,
            "service_category": "competitor_analysis",
            "service_name": "In-Depth Competitive SEO Audit",
            "scope_details": "40-page competitive audit with real domain rankings",
            "tier": "standard",
            "units": 1
        },
        timeout=10.0
    )
    quote_data = quote_resp.json()

    # 3. Sign proposal
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
        "justification": f"Procuring competitive benchmark from {quote_data['merchant_name']}. Rate ${quote_data['amount']:.2f} requires human approval.",
        "quote_details": quote_data
    }
    signature = agent_key_manager.sign_proposal(role="service", payload=proposal_dict)

    # 4. Propose transaction
    propose_resp = httpx.post(
        f"{BASE_API}/transactions/propose",
        headers=headers,
        json={"proposal": proposal_dict, "signature": signature},
        timeout=15.0
    )
    tx_id = propose_resp.json()["transaction"]["id"]
    print(f"Created pending transaction {tx_id} on task {task_id}")

    # 5. Playwright Screenshot
    from playwright.sync_api import sync_playwright
    print("Launching Chromium to capture Trust Review screen...")
    os.makedirs("reports", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()

        # Login
        print("Logging in to web UI...")
        page.goto(f"{WEB_URL}/login")
        page.wait_for_selector('button:has-text("Continue with Email")')
        page.click('button:has-text("Continue with Email")')
        page.fill('input[type="email"]', USER_EMAIL)
        page.fill('input[type="password"]', USER_PASSWORD)
        page.click('button:has-text("Sign In")')

        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=10000)
        except Exception:
            pass

        time.sleep(3)

        # Navigate to Task Page
        print(f"Navigating to {WEB_URL}/tasks/{task_id}...")
        page.goto(f"{WEB_URL}/tasks/{task_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector('text=Trust Review', timeout=20000)
        time.sleep(5)

        shot_path = "reports/phase4_trust_review_card.png"
        page.screenshot(path=shot_path, full_page=True)
        print(f"Saved screenshot: {shot_path}")

        # Also copy to artifacts directory
        artifact_dir = r"C:\Users\Gauri Gotmare\.gemini\antigravity\brain\625a4030-a1db-4934-b238-1123f9268d00"
        os.makedirs(artifact_dir, exist_ok=True)
        artifact_path = os.path.join(artifact_dir, "phase4_trust_review_card.png")
        import shutil
        shutil.copyfile(shot_path, artifact_path)
        print(f"Copied to artifact path: {artifact_path}")

        browser.close()
        print("Phase 4 screenshot capture complete!")

if __name__ == "__main__":
    capture_phase4()

