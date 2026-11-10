import os
import sys
import time
import shutil
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from app.db.supabase import get_supabase_admin_client

WEB_URL = "http://localhost:3000"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASSWORD = "NirbharSecurePass2026!"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARTIFACT_DIR = r"C:\Users\Gauri Gotmare\.gemini\antigravity\brain\625a4030-a1db-4934-b238-1123f9268d00"

def capture_screenshots():
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    # Find the latest completed transaction for the payment result screen
    supabase = get_supabase_admin_client()
    tx_rows = supabase.table("transactions").select("id, status").order("created_at", desc=True).limit(5).execute().data
    tx_id = tx_rows[0]["id"] if tx_rows else "test-tx-id"
    for r in tx_rows:
        if r.get("status") == "COMPLETED":
            tx_id = r["id"]
            break

    print(f"Selected Transaction ID for Payment Result Screen: {tx_id}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 950})
        page = context.new_page()

        # 1. Log in through the UI
        print("Logging in to web UI...")
        page.goto(f"{WEB_URL}/login")
        page.wait_for_selector('button:has-text("Continue with Email")')
        page.click('button:has-text("Continue with Email")')
        page.fill('input[type="email"]', USER_EMAIL)
        page.fill('input[type="password"]', USER_PASSWORD)
        page.click('button:has-text("Sign In")')

        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=12000)
        except Exception:
            pass

        time.sleep(3)

        # 2. Capture Payment Result Screen
        print(f"Navigating to Payment Result screen: {WEB_URL}/payments/result?tx_id={tx_id}...")
        page.goto(f"{WEB_URL}/payments/result?tx_id={tx_id}")
        page.wait_for_load_state("networkidle")
        time.sleep(4)

        result_path = os.path.join(reports_dir, "phase5_payment_result_screen.png")
        page.screenshot(path=result_path, full_page=True)
        print(f"Captured Payment Result Screen: {result_path}")

        artifact_result = os.path.join(ARTIFACT_DIR, "phase5_payment_result_screen.png")
        shutil.copyfile(result_path, artifact_result)

        # 3. Capture Transactions Page
        print(f"Navigating to Transactions page: {WEB_URL}/transactions...")
        page.goto(f"{WEB_URL}/transactions")
        page.wait_for_load_state("networkidle")
        time.sleep(4)

        tx_path = os.path.join(reports_dir, "phase5_transactions_page.png")
        page.screenshot(path=tx_path, full_page=True)
        print(f"Captured Transactions Page: {tx_path}")

        artifact_tx = os.path.join(ARTIFACT_DIR, "phase5_transactions_page.png")
        shutil.copyfile(tx_path, artifact_tx)

        browser.close()
        print("All Phase 5 screenshots captured successfully!")

if __name__ == "__main__":
    capture_screenshots()
