import os
import re
import sys
import time
import shutil
import httpx
from playwright.sync_api import sync_playwright

USER_A_EMAIL = "user_a_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"
BASE_URL = "http://localhost:3000"
API_URL = "http://127.0.0.1:8000"

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
ENV_BAK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.bak"))

def run():
    print("=" * 80)
    print("CAPTURING KILLED GEMINI KEY ADVERSARIAL ERROR FLOW")
    print("=" * 80)

    # 1. Verify health shows Gemini error
    health_res = httpx.get(f"{API_URL}/health", timeout=10.0)
    print(f"Health response code: {health_res.status_code}")
    print(f"Gemini service: {health_res.json().get('services', {}).get('gemini')}")

    # 2. Browser flow
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Log in
        print("\nLogging into Nirbhar AI as User A...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector('button:has-text("Continue with Email")')
        page.click('button:has-text("Continue with Email")')
        page.fill('input[type="email"]', USER_A_EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button:has-text("Sign In")')
        page.wait_for_url(f"{BASE_URL}/", timeout=15000)

        # Create Task with killed key
        print("\nCreating task with killed Gemini key...")
        page.goto(f"{BASE_URL}/tasks/new")
        page.wait_for_selector('text=Create Autonomous Task')
        page.fill('textarea', "Security Audit & Penetration Testing: Check token validation and IAM policies")
        page.fill('input[inputmode="decimal"]', "45.00")
        page.click('button:has-text("Start Task")')

        # Wait for redirect
        page.wait_for_url(re.compile(r".*/tasks/[a-f0-9-]+"), timeout=20000)
        task_url = page.url
        task_id = task_url.split("/tasks/")[-1].split("?")[0]
        print(f"Task created: ID={task_id}")

        # Wait for FAILED status
        print("Waiting for Coordinator Agent to fail closed...")
        page.wait_for_selector('text=FAILED', timeout=30000)
        page.wait_for_selector('text=Execution Failed', timeout=10000)
        time.sleep(2)

        err_screenshot = "reports/phase2_gemini_key_killed_error.png"
        page.screenshot(path=err_screenshot)
        print(f"[PASSED] Error screenshot saved: {err_screenshot}")

        # Open proof drawer
        print("Opening Proof Drawer on failed run...")
        proof_chip = page.locator('button[title="View verifiable proof & raw telemetry"]').first
        proof_chip.click()
        page.wait_for_selector('text=Raw Upstream Payload', timeout=5000)
        time.sleep(1)

        drawer_screenshot = "reports/phase2_gemini_key_killed_drawer.png"
        page.screenshot(path=drawer_screenshot)
        print(f"[PASSED] Drawer screenshot saved: {drawer_screenshot}")

        browser.close()

    # 3. Restore genuine .env
    print("\nRestoring genuine .env from .env.bak...")
    if os.path.exists(ENV_BAK_PATH):
        shutil.copyfile(ENV_BAK_PATH, ENV_PATH)
        print("  Original .env restored!")

    print("[DONE] Step 5 error flow captured!")

if __name__ == "__main__":
    run()

