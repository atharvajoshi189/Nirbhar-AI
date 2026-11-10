import os
import sys
import time
from playwright.sync_api import sync_playwright

TASK_ID = "71574ff4-c310-403e-aac8-ed6f16d72d6b"
USER_EMAIL = "user_a_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"
BASE_URL = "http://localhost:3000"

def capture_screenshots():
    print(f"Connecting to {BASE_URL} to capture Phase 3 screenshots...")
    os.makedirs("reports", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        # Step 1: Login
        print("Signing in...")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector('button:has-text("Continue with Email")')
        page.click('button:has-text("Continue with Email")')
        page.fill('input[type="email"]', USER_EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button:has-text("Sign In")')
        
        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=10000)
            print("Successfully navigated to:", page.url)
        except Exception as e:
            print("Warning on navigation wait:", e)
        
        time.sleep(3)

        # Step 2: Navigate to Phase 3 Task
        print(f"Navigating to task {TASK_ID}...")
        page.goto(f"{BASE_URL}/tasks/{TASK_ID}")
        page.wait_for_selector('text=Discovered Market Providers', timeout=20000)
        time.sleep(3)

        # Capture Task Overview
        shot1_path = "reports/phase3_task_overview.png"
        page.screenshot(path=shot1_path, full_page=True)
        print(f"Saved: {shot1_path}")

        # Step 3: Open Proof Drawer
        print("Opening Proof Drawer...")
        proof_btn = page.query_selector('button:has-text("Tavily + Gemini")')
        if proof_btn:
            proof_btn.click()
            time.sleep(2)
            shot2_path = "reports/phase3_proof_drawer.png"
            page.screenshot(path=shot2_path)
            print(f"Saved: {shot2_path}")

            # Close drawer
            close_btn = page.query_selector('button:has-text("Close"), button[aria-label="Close"]')
            if close_btn:
                close_btn.click()
                time.sleep(1)

        # Step 4: Transactions Page
        print("Navigating to /transactions...")
        page.goto(f"{BASE_URL}/transactions")
        try:
            page.wait_for_selector('text=APPROVED', timeout=15000)
        except Exception:
            print("Notice: 'APPROVED' text not found immediately, continuing...")
        time.sleep(3)
        shot3_path = "reports/phase3_transactions_page.png"
        page.screenshot(path=shot3_path)
        print(f"Saved: {shot3_path}")

        browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    capture_screenshots()
