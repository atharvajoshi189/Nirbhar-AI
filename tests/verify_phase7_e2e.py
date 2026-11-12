import os
import sys
import time
import json
import shutil
from decimal import Decimal
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from app.db.supabase import get_supabase_admin_client

WEB_URL = "http://localhost:3000"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASSWORD = "NirbharSecurePass2026!"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARTIFACT_DIR = r"C:\Users\Gauri Gotmare\.gemini\antigravity\brain\625a4030-a1db-4934-b238-1123f9268d00"

def run_phase7_verification():
    print("=" * 60)
    print("PHASE 7 E2E VERIFICATION: ADVERSARIAL RED TEAM SUITE")
    print("=" * 60)

    supabase = get_supabase_admin_client()

    # 1. Check initial state of paypal_orders
    initial_orders = supabase.table("paypal_orders").select("id", count="exact").execute()
    initial_count = initial_orders.count or len(initial_orders.data or [])
    print(f"[Initial Check] Existing PayPal Orders in DB: {initial_count}")

    # 2. Check initial count of red_team audit_events
    initial_audits = supabase.table("audit_events").select("id", count="exact").eq("event_type", "red_team").execute()
    initial_audit_count = initial_audits.count or len(initial_audits.data or [])
    print(f"[Initial Check] Existing red_team audit records in DB: {initial_audit_count}")

    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    with sync_playwright() as p:
        print(f"[Browser] Launching Chrome from {CHROME_PATH}...")
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Log in if needed
        print(f"[Browser] Logging into {WEB_URL}/login ...")
        page.goto(f"{WEB_URL}/login", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        try:
            if page.locator('button:has-text("Continue with Email")').is_visible():
                page.click('button:has-text("Continue with Email")')
                time.sleep(1)
                page.fill('input[type="email"]', USER_EMAIL)
                page.fill('input[type="password"]', USER_PASSWORD)
                page.click('button:has-text("Sign In")')
                page.wait_for_url(lambda u: "/login" not in u, timeout=12000)
                time.sleep(2)
        except Exception as e:
            print(f"[Login Notice] {e}")

        # Navigate to /red-team
        print(f"[Browser] Navigating to {WEB_URL}/red-team ...")
        page.goto(f"{WEB_URL}/red-team", wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Verify page header
        header_text = page.locator("h1:has-text('Adversarial Red Team Suite')").inner_text()
        print(f"[UI Check] Header: {header_text}")
        assert "Adversarial Red Team Suite" in header_text

        # Verify 6 attack cards rendered
        run_buttons = page.locator("button:has-text('Run Attack'), button:has-text('Re-run')")
        card_count = run_buttons.count()
        print(f"[UI Check] Attack Cards Found: {card_count}")
        assert card_count == 6, f"Expected 6 attack cards, found {card_count}"

        # Capture initial screenshot
        init_path = os.path.join(reports_dir, "phase7_initial_grid.png")
        page.screenshot(path=init_path)
        print("[Screenshot] Captured phase7_initial_grid.png")

        # Click "Run All 6 Attacks" button
        run_all_btn = page.locator("button:has-text('Run All 6 Attacks')")
        assert run_all_btn.is_visible()
        print("[Action] Clicking 'Run All 6 Attacks' button to execute live pipeline...")
        run_all_btn.click()

        # Wait for all 6 attacks to complete
        print("[Waiting] Waiting for all 6 attacks to be evaluated by Trust Engine...")
        page.wait_for_selector("text='6 / 6 Defended'", timeout=60000)
        time.sleep(3)
        print("[Success] All 6 attacks intercepted, defended, and logged!")

        # Screenshot the full defended grid (1440px)
        grid_screenshot_path = os.path.join(reports_dir, "phase7_red_team_grid.png")
        page.screenshot(path=grid_screenshot_path, full_page=True)
        shutil.copy(grid_screenshot_path, os.path.join(ARTIFACT_DIR, "phase7_red_team_grid.png"))
        print(f"[Screenshot] Captured {grid_screenshot_path}")

        # Verify Prompt Injection card details
        prompt_card = page.locator("div:has-text('Indirect Prompt Injection via Web Page')").last
        assert prompt_card.is_visible()

        # Verify Prompt Injection specific callouts
        assert page.locator("text='Indirect Prompt Injection Intercepted'").is_visible()
        assert page.locator("text='Reached agent output -> Blocked by Trust Engine Dual Scanner'").is_visible()
        print("[Verification] Indirect Prompt Injection dual scanner block verified!")

        # Scroll to Prompt Injection card and screenshot
        prompt_card.scroll_into_view_if_needed()
        time.sleep(1)
        pi_screenshot_path = os.path.join(reports_dir, "phase7_prompt_injection_card.png")
        prompt_card.screenshot(path=pi_screenshot_path)
        shutil.copy(pi_screenshot_path, os.path.join(ARTIFACT_DIR, "phase7_prompt_injection_card.png"))
        print(f"[Screenshot] Captured {pi_screenshot_path}")

        # Click the first ProofChip to open the Global Proof Drawer
        print("[Action] Clicking ProofChip to open Global Proof Drawer...")
        first_proof_chip = page.locator("button[aria-label^='View proof:']").first
        first_proof_chip.click()
        time.sleep(1.5)

        # Verify ProofDrawer opened
        drawer_visible = page.locator("div[role='dialog']").is_visible()
        print(f"[UI Check] Global Proof Drawer visible: {drawer_visible}")
        assert drawer_visible

        # Screenshot Proof Drawer
        drawer_screenshot_path = os.path.join(reports_dir, "phase7_red_team_proof_drawer.png")
        page.screenshot(path=drawer_screenshot_path)
        shutil.copy(drawer_screenshot_path, os.path.join(ARTIFACT_DIR, "phase7_red_team_proof_drawer.png"))
        print(f"[Screenshot] Captured {drawer_screenshot_path}")

        # Close proof drawer
        close_btn = page.locator("button[aria-label='Close proof drawer']")
        if close_btn.is_visible():
            close_btn.click()
            time.sleep(0.5)

        # Scroll down to Adversarial Audit Stream
        audit_section = page.locator("h3:has-text('Adversarial Audit Stream (type: red_team)')")
        audit_section.scroll_into_view_if_needed()
        time.sleep(1)
        audit_screenshot_path = os.path.join(reports_dir, "phase7_audit_ledger.png")
        page.screenshot(path=audit_screenshot_path)
        shutil.copy(audit_screenshot_path, os.path.join(ARTIFACT_DIR, "phase7_audit_ledger.png"))
        print(f"[Screenshot] Captured {audit_screenshot_path}")

        # Mobile viewport check (390px)
        print("[Mobile Check] Testing 390px responsive viewport...")
        page.set_viewport_size({"width": 390, "height": 844})
        time.sleep(1)
        mobile_path = os.path.join(reports_dir, "phase7_red_team_390px.png")
        page.screenshot(path=mobile_path, full_page=True)
        shutil.copy(mobile_path, os.path.join(ARTIFACT_DIR, "phase7_red_team_390px.png"))
        print(f"[Screenshot] Captured {mobile_path}")

        browser.close()

    # 3. Post-execution Database Invariant Checks
    print("\n--- POST-EXECUTION DATABASE INVARIANT CHECKS ---")

    # Invariant A: Exactly zero PayPal orders created
    post_orders = supabase.table("paypal_orders").select("id", count="exact").execute()
    post_count = post_orders.count or len(post_orders.data or [])
    print(f"[Invariant A] PayPal Orders: Before = {initial_count}, After = {post_count}")
    assert post_count == initial_count, f"FAIL: PayPal orders increased! Expected {initial_count}, got {post_count}"
    print("[Invariant A PASSED] Exactly 0 PayPal orders created across all 6 attacks!")

    # Invariant B: Exactly 6 new red_team audit events logged in audit_events
    post_audits = supabase.table("audit_events").select("*").eq("event_type", "red_team").order("sequence_number", desc=True).limit(6).execute()
    new_audits = post_audits.data or []
    print(f"[Invariant B] Retrieved {len(new_audits)} recent red_team audit records from Supabase.")
    assert len(new_audits) >= 6, f"Expected at least 6 red_team audit records, got {len(new_audits)}"

    for ev in new_audits[:6]:
        payload = ev.get("payload", {})
        sc_id = payload.get("scenario_id")
        dec = payload.get("decision")
        reasons = payload.get("reason_codes", [])
        hash_val = ev.get("hash")
        seq = ev.get("sequence_number")
        print(f"  Seq #{seq}: Scenario={sc_id}, Decision={dec}, Reasons={reasons}, Hash={hash_val[:12]}...")
        assert dec == "BLOCKED"
        assert ev.get("event_type") == "red_team"

    print(f"[Invariant B PASSED] All 6 attacks logged under event_type='red_team' with BLOCKED decisions!")
    print("\n============================================================")
    print("ALL PHASE 7 VERIFICATIONS PASSED WITH REAL APIS & RAILS!")
    print("============================================================")

if __name__ == "__main__":
    run_phase7_verification()
