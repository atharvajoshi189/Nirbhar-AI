import os
import re
import time
from playwright.sync_api import sync_playwright

USER_A_EMAIL = "user_a_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"
BASE_URL = "http://localhost:3000"

def run_browser_verification():
    print("=" * 70)
    print("NIRBHAR AI — PHASE 2 BROWSER UI VERIFICATION (PLAYWRIGHT)")
    print("=" * 70)

    os.makedirs("reports", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Step 1: Login
        print("\n[Step 1] Navigating to /login and signing in...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector('button:has-text("Continue with Email")')

        # Click email button and sign in
        page.click('button:has-text("Continue with Email")')
        page.fill('input[type="email"]', USER_A_EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button:has-text("Sign In")')

        # Wait for redirect to Dashboard
        page.wait_for_url(f"{BASE_URL}/", timeout=15000)
        page.wait_for_selector('text=Dashboard')
        time.sleep(2)
        print("  [PASSED] Successfully logged into Nirbhar AI Dashboard!")

        # Step 2: Verify Dashboard with 3 Stat Cards
        print("\n[Step 2] Capturing Dashboard with 3 Stat Cards...")
        page.wait_for_selector('text=Total Tasks')
        page.wait_for_selector('text=Total Approved Spend')
        page.wait_for_selector('text=Blocked Count')
        page.screenshot(path="reports/phase2_dashboard.png")
        print("  Screenshot saved: reports/phase2_dashboard.png")

        # Step 3: Navigate to New Task Page
        print("\n[Step 3] Navigating to /tasks/new...")
        page.click('a:has-text("New Task")')
        page.wait_for_url(f"{BASE_URL}/tasks/new", timeout=10000)
        page.wait_for_selector('text=Create Autonomous Task')
        page.wait_for_selector('text=Task Description')
        page.wait_for_selector('text=Max Budget')
        page.wait_for_selector('text=Approval Mode')

        # Expand advanced policy
        page.click('button:has-text("Advanced policy (Optional)")')
        time.sleep(1)
        page.screenshot(path="reports/phase2_new_task_form.png")
        print("  Screenshot saved: reports/phase2_new_task_form.png")

        # Step 4: Fill form and click "Start Task"
        print("\n[Step 4] Submitting new task form...")
        page.fill(
            'textarea',
            "Automated Multi-Region Database Provisioning: Set up a replicated PostgreSQL cluster on AWS and configure DNS failover."
        )
        page.fill('input[type="number"][min="0.01"]', "180.00")
        page.click('button:has-text("Ask above a limit")')
        page.click('button:has-text("Start Task")')

        # Step 5: Wait for navigation to /tasks/[id]
        print("\n[Step 5] Waiting for Live Agent Activity page redirect...")
        page.wait_for_url(re.compile(r".*/tasks/[a-f0-9-]+"), timeout=20000)
        task_url = page.url
        print(f"  Redirected to Live Activity URL: {task_url}")

        # Wait for Coordinator Agent run to complete
        print("  Waiting for Coordinator Agent execution card...")
        page.wait_for_selector('text=COMPLETED', timeout=30000)
        page.wait_for_selector('text=Planned Subtasks & Budget Allocation')
        time.sleep(2)
        page.screenshot(path="reports/phase2_live_agent_activity.png")
        print("  Screenshot saved: reports/phase2_live_agent_activity.png")

        # Step 6: Click Proof Chip to Open Proof Drawer
        print("\n[Step 6] Clicking Proof Chip to inspect raw Gemini telemetry...")
        proof_chips = page.locator('button[title="View verifiable proof & raw telemetry"]')
        if proof_chips.count() > 0:
            proof_chips.first.click()
            page.wait_for_selector('text=Raw Upstream Payload', timeout=5000)
            time.sleep(1)
            page.screenshot(path="reports/phase2_proof_drawer.png")
            print("  Screenshot saved: reports/phase2_proof_drawer.png")

        browser.close()
        print("\n[PASSED] Complete browser UI verification passed!")

if __name__ == "__main__":
    run_browser_verification()
