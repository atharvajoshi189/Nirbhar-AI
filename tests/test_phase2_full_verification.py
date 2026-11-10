import os
import re
import sys
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

# Ensure api in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.db.supabase import get_supabase_admin_client

USER_A_EMAIL = "user_a_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"
BASE_URL = "http://localhost:3000"

def run_full_verification():
    print("=" * 80)
    print("NIRBHAR AI — PHASE 2 FULL VERIFICATION IN REAL BROWSER")
    print("=" * 80)

    os.makedirs("reports", exist_ok=True)
    supabase = get_supabase_admin_client()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Step 0: Sign in
        print("\n[Step 0] Logging into Nirbhar AI as User A...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector('button:has-text("Continue with Email")')
        page.click('button:has-text("Continue with Email")')
        page.fill('input[type="email"]', USER_A_EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button:has-text("Sign In")')
        page.wait_for_url(f"{BASE_URL}/", timeout=15000)
        print("  [PASSED] Logged in successfully!")

        # ----------------------------------------------------------------------
        # REQUIREMENT 1 & 2: Create task "Prepare a competitor research report for my startup, max $20"
        # ----------------------------------------------------------------------
        print("\n[Requirement 1 & 2] Creating task 'Prepare a competitor research report for my startup, max $20'...")
        page.goto(f"{BASE_URL}/tasks/new")
        page.wait_for_selector('text=Create Autonomous Task')

        # Fill 4 fields
        page.fill('textarea', "Prepare a competitor research report for my startup, max $20")
        page.fill('input[inputmode="decimal"]', "20.00")
        page.click('button:has-text("Ask above a limit")')

        # Click Start Task
        page.click('button:has-text("Start Task")')

        # Wait for redirect to /tasks/[id]
        page.wait_for_url(re.compile(r".*/tasks/[a-f0-9-]+"), timeout=20000)
        task_url = page.url
        task_id = task_url.split("/tasks/")[-1].split("?")[0]
        print(f"  Created Task ID: {task_id}")
        print(f"  Live Activity URL: {task_url}")

        # Wait for Coordinator Agent to finish execution
        print("  Waiting for real Gemini call and planned subtasks...")
        page.wait_for_selector('text=COMPLETED', timeout=35000)
        page.wait_for_selector('text=Planned Subtasks & Budget Allocation', timeout=10000)
        time.sleep(2)

        # Screenshot of the completed plan
        plan_screenshot = "reports/phase2_competitor_research_plan.png"
        page.screenshot(path=plan_screenshot)
        print(f"  [PASSED] Plan screenshot saved to: {plan_screenshot}")

        # Requirement 2: Open raw response drawer and confirm real model name and latency
        print("\n  Opening raw response drawer...")
        proof_chip = page.locator('button[title="View verifiable proof & raw telemetry"]').first
        proof_chip.click()
        page.wait_for_selector('text=Raw Upstream Payload', timeout=5000)
        page.wait_for_selector('text=Roundtrip Latency', timeout=5000)
        time.sleep(1)

        # Check drawer text content for model and latency
        drawer_content = page.locator('div[role="dialog"]').inner_text()
        assert "models/gemini-3.5-flash-lite" in drawer_content or "gemini" in drawer_content, "Real Gemini model not found in drawer!"
        assert "ms" in drawer_content, "Latency not found in drawer!"
        print("  [PASSED] Drawer confirmed: real Gemini model name and roundtrip latency verified!")

        drawer_screenshot = "reports/phase2_competitor_research_proof_drawer.png"
        page.screenshot(path=drawer_screenshot)
        print(f"  [PASSED] Proof drawer screenshot saved to: {drawer_screenshot}")

        # Dismiss drawer
        page.click('button:has-text("Dismiss")')
        time.sleep(0.5)

        # ----------------------------------------------------------------------
        # REQUIREMENT 3: Confirm task and policy rows exist in Supabase
        # ----------------------------------------------------------------------
        print("\n[Requirement 3] Verifying database records in Supabase...")
        task_res = supabase.table("tasks").select("*").eq("id", task_id).execute()
        assert task_res.data and len(task_res.data) > 0, f"Task {task_id} not found in Supabase!"
        task_db = task_res.data[0]
        print(f"  [Supabase tasks] Found row: ID={task_db['id']}, Title='{task_db['title']}', Budget={task_db['budget_max']} {task_db['currency']}, Status={task_db['status']}")
        assert float(task_db["budget_max"]) == 20.00
        assert task_db["currency"] == "USD"
        assert task_db["status"] == "ACTIVE"

        policy_res = supabase.table("task_policies").select("*").eq("task_id", task_id).execute()
        assert policy_res.data and len(policy_res.data) > 0, f"Task policy for {task_id} not found in Supabase!"
        policy_db = policy_res.data[0]
        print(f"  [Supabase task_policies] Found row: Policy ID={policy_db['id']}, Auto-Approve Threshold={policy_db['auto_approve_threshold']}, Single Tx Limit={policy_db['single_tx_limit']}, Strict Mode={policy_db['strict_mode']}")
        assert float(policy_db["auto_approve_threshold"]) <= 20.00

        run_res = supabase.table("agent_runs").select("*").eq("task_id", task_id).execute()
        assert run_res.data and len(run_res.data) > 0, f"Agent run for {task_id} not found in Supabase!"
        run_db = run_res.data[0]
        print(f"  [Supabase agent_runs] Found row: Run ID={run_db['id']}, Model='{run_db['model_name']}', Latency={run_db['latency_ms']}ms, Status={run_db['status']}, Tokens={run_db['prompt_tokens']} prompt / {run_db['completion_tokens']} completion")
        assert run_db["status"] == "COMPLETED"
        assert run_db["latency_ms"] > 0
        print("  [PASSED] Supabase authoritative records confirmed!")

        # ----------------------------------------------------------------------
        # REQUIREMENT 4: Submit empty form and invalid budget (negative, text)
        # ----------------------------------------------------------------------
        print("\n[Requirement 4] Testing validation error states on New Task form...")
        page.goto(f"{BASE_URL}/tasks/new")
        page.wait_for_selector('text=Create Autonomous Task')

        # 4a: Empty form submission
        print("  Submitting completely empty form...")
        page.fill('textarea', "")
        page.fill('input[inputmode="decimal"]', "")
        page.click('button:has-text("Start Task")')
        page.wait_for_selector('text=Task description is required', timeout=5000)
        empty_screenshot = "reports/phase2_empty_form_error.png"
        page.screenshot(path=empty_screenshot)
        print(f"  [PASSED] Empty form error screenshot: {empty_screenshot}")

        # 4b: Negative budget submission
        print("  Submitting negative budget (-20.00)...")
        page.fill('textarea', "Valid task description for negative budget test")
        page.fill('input[inputmode="decimal"]', "-20.00")
        page.click('button:has-text("Start Task")')
        page.wait_for_selector('text=Please enter a valid positive numerical budget ceiling', timeout=5000)
        neg_screenshot = "reports/phase2_negative_budget_error.png"
        page.screenshot(path=neg_screenshot)
        print(f"  [PASSED] Negative budget error screenshot: {neg_screenshot}")

        # 4c: Text budget submission
        print("  Submitting text budget ('twenty dollars')...")
        page.fill('textarea', "Valid task description for text budget test")
        page.fill('input[inputmode="decimal"]', "twenty dollars")
        page.click('button:has-text("Start Task")')
        page.wait_for_selector('text=Please enter a valid positive numerical budget ceiling', timeout=5000)
        text_screenshot = "reports/phase2_text_budget_error.png"
        page.screenshot(path=text_screenshot)
        print(f"  [PASSED] Text budget error screenshot: {text_screenshot}")

        browser.close()

    print("\n[PASSED] Real browser automated flow requirements 1-4 completed successfully!")

if __name__ == "__main__":
    run_full_verification()

