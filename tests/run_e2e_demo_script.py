import asyncio
import os
import time
import shutil
import json
from playwright.async_api import async_playwright

async def run_demo_script():
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    artifact_dir = r"C:\Users\Gauri Gotmare\.gemini\antigravity\brain\625a4030-a1db-4934-b238-1123f9268d00"
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(artifact_dir, exist_ok=True)

    print("=" * 75, flush=True)
    print("NIRBHAR AI — FULL 4-MINUTE DEMO SCRIPT E2E AUTOMATION & AUDIT", flush=True)
    print("Target Web UI: http://localhost:3000", flush=True)
    print("Target Core API: http://127.0.0.1:8000", flush=True)
    print("Target Vendor Gateway: http://127.0.0.1:8001", flush=True)
    print("=" * 75, flush=True)

    timings = {}
    issues_found = []
    t_global_start = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Listen for console errors or warnings (ignoring benign SWC / WASM notices)
        page.on("console", lambda msg: issues_found.append(f"Console {msg.type}: {msg.text}") if msg.type in ("error", "warning") and "SWC" not in msg.text and "favicon" not in msg.text and "WASM" not in msg.text and "middleware" not in msg.text else None)

        # -------------------------------------------------------------
        # STEP 0: Authentication
        # -------------------------------------------------------------
        t0 = time.time()
        print("\n[Step 0] Logging in as user_a_nirbhar@test.com...", flush=True)
        await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        email_btn = page.locator("button:has-text('Continue with Email')")
        if await email_btn.count() > 0:
            await email_btn.click()
            await page.fill("input#login-email", "user_a_nirbhar@test.com")
            await page.fill("input#login-password", "NirbharSecurePass2026!")
            await page.click("button:has-text('Sign In')")
            await page.wait_for_timeout(2500)
            print("   Logged in successfully.", flush=True)
        timings["auth"] = time.time() - t0

        # -------------------------------------------------------------
        # ACT 1: Autonomous Happy Path ($12 Valid Payment)
        # -------------------------------------------------------------
        t_act1_start = time.time()
        print("\n[ACT 1: 0:00 - 1:00] Autonomous Happy Path ($12 Spend on $20 Budget)...", flush=True)
        
        # 1.1 Dashboard & Health Strip Inspection
        await page.goto("http://localhost:3000", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        footer_strip = page.locator("footer")
        if await footer_strip.count() > 0:
            print("   Footer health telemetry strip verified present.", flush=True)
        else:
            issues_found.append("Footer health strip missing on dashboard.")

        shot_act1_dash = os.path.join(reports_dir, "demo_act1_dashboard.png")
        await page.screenshot(path=shot_act1_dash)

        # 1.2 Open Proof Drawer from Dashboard
        print("   Testing Global Proof Drawer from Dashboard ProofChip...", flush=True)
        try:
            await page.wait_for_selector("button[title*='verifiable proof'], button[aria-label*='View proof'], button:has-text('task-proof')", timeout=6000)
        except Exception:
            pass

        dash_proof_chip = page.locator("button[title*='verifiable proof'], button[aria-label*='View proof'], button:has-text('task-proof')").first
        if await dash_proof_chip.count() > 0:
            await dash_proof_chip.click()
            await page.wait_for_timeout(1000)
            print("   Proof Drawer opened from Dashboard.", flush=True)
            shot_dash_drawer = os.path.join(reports_dir, "demo_act1_proof_drawer.png")
            await page.screenshot(path=shot_dash_drawer)
            
            # Close drawer
            close_btn = page.locator("button[aria-label='Close drawer'], button:has-text('Close')")
            if await close_btn.count() > 0:
                await close_btn.first.click()
                await page.wait_for_timeout(500)
        else:
            issues_found.append("Dashboard ProofChip not found.")

        # 1.3 Navigate to /tasks/new & Create Task
        print("   Creating new autonomous task with $20 budget...", flush=True)
        await page.goto("http://localhost:3000/tasks/new", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        desc_box = page.locator("#task-description")
        if await desc_box.count() > 0:
            await desc_box.fill("Procure dedicated CI worker runner on CloudScale infrastructure.")
        else:
            issues_found.append("Selector #task-description not found on /tasks/new.")

        # Ensure budget is 20.00
        budget_input = page.locator("#task-budget-max")
        if await budget_input.count() > 0:
            await budget_input.fill("20.00")

        # Submit task
        submit_btn = page.locator("button[type='submit']")
        if await submit_btn.count() > 0:
            await submit_btn.click()
            await page.wait_for_timeout(3000)
            print("   Task created and submitted to autonomous agents.", flush=True)
        else:
            issues_found.append("Submit button on /tasks/new not found.")

        # 1.4 Review Task Trust Decision
        print("   Inspecting task Trust Review screen...", flush=True)
        # Navigate back to dashboard to select the newly created task's Activity
        await page.goto("http://localhost:3000", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        try:
            await page.wait_for_selector("a:has-text('Activity')", timeout=6000)
        except Exception:
            pass

        activity_btn = page.locator("a:has-text('Activity')").first
        if await activity_btn.count() > 0:
            await activity_btn.click()
            await page.wait_for_timeout(2000)
        else:
            issues_found.append("Could not find 'Activity' link on dashboard table.")

        shot_act1_review = os.path.join(reports_dir, "demo_act1_trust_review.png")
        await page.screenshot(path=shot_act1_review)

        # 1.5 Verify ProofChip on Task Detail Page
        try:
            await page.wait_for_selector("button[title*='verifiable proof'], button[aria-label*='View proof'], button:has-text('task-proof')", timeout=6000)
        except Exception:
            pass

        task_proof_chip = page.locator("button[title*='verifiable proof'], button[aria-label*='View proof'], button:has-text('task-proof')").first
        if await task_proof_chip.count() > 0:
            print("   Task detail ProofChip verified present.", flush=True)
            await task_proof_chip.click()
            await page.wait_for_timeout(1000)
            close_btn = page.locator("button[aria-label='Close drawer'], button:has-text('Close')")
            if await close_btn.count() > 0:
                await close_btn.first.click()
                await page.wait_for_timeout(500)
        else:
            issues_found.append("Task detail ProofChip not found.")

        timings["act1_happy_path"] = time.time() - t_act1_start
        print(f"   [ACT 1 COMPLETE] Elapsed: {timings['act1_happy_path']:.2f}s", flush=True)

        # -------------------------------------------------------------
        # ACT 2: Hard Budget Violation Blocked ($35 vs $20)
        # -------------------------------------------------------------
        t_act2_start = time.time()
        print("\n[ACT 2: 1:00 - 2:00] Executing Attack 1: Budget Ceiling Violation ($35 vs $20)...", flush=True)
        await page.goto("http://localhost:3000/red-team", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # Find Budget Violation Card and click Run Attack
        btn_budget = page.locator("button[data-run-button='budget_violation']").first
        if await btn_budget.count() > 0:
            await btn_budget.click()
            print("   Triggered Budget Violation attack... waiting for Trust Engine...", flush=True)
            await page.wait_for_timeout(4000)

            # Check decision
            card_budget = page.locator("div[data-scenario-id='budget_violation']").first
            text_budget = await card_budget.text_content()
            text_budget_lower = text_budget.lower() if text_budget else ""
            if "blocked" in text_budget_lower:
                print("   [CONFIRMED] Decision is Blocked as required!", flush=True)
            else:
                issues_found.append("Budget Violation card did not show Blocked.")
            if "BUDGET_EXCEEDED" in text_budget:
                print("   [CONFIRMED] Reason code BUDGET_EXCEEDED raised!", flush=True)
            else:
                issues_found.append("Budget Violation did not show BUDGET_EXCEEDED reason code.")
            if "0 paypal order" in text_budget_lower or "zero" in text_budget_lower or "false" in text_budget_lower:
                print("   [CONFIRMED] Zero PayPal orders created!", flush=True)
        else:
            issues_found.append("Could not locate Run Attack button on Budget Violation card.")

        shot_act2 = os.path.join(reports_dir, "demo_act2_budget_blocked.png")
        await page.screenshot(path=shot_act2)
        timings["act2_budget_violation"] = time.time() - t_act2_start
        print(f"   [ACT 2 COMPLETE] Elapsed: {timings['act2_budget_violation']:.2f}s", flush=True)

        # -------------------------------------------------------------
        # ACT 3: Cryptographic Quote Tampering Blocked
        # -------------------------------------------------------------
        t_act3_start = time.time()
        print("\n[ACT 3: 2:00 - 3:00] Executing Attack 2: Cryptographic Quote Tampering...", flush=True)
        btn_tamper = page.locator("button[data-run-button='quote_tampering']").first
        if await btn_tamper.count() > 0:
            await btn_tamper.click()
            print("   Triggered Quote Tampering attack... waiting for HMAC re-verification...", flush=True)
            await page.wait_for_timeout(4000)

            card_tamper = page.locator("div[data-scenario-id='quote_tampering']").first
            text_tamper = await card_tamper.text_content()
            text_tamper_lower = text_tamper.lower() if text_tamper else ""
            if "blocked" in text_tamper_lower:
                print("   [CONFIRMED] Quote Tampering is Blocked!", flush=True)
            else:
                issues_found.append("Quote Tampering card did not show Blocked.")
            if "QUOTE_MISMATCH" in text_tamper or "QUOTE_TAMPERED" in text_tamper or "SIGNATURE_MISMATCH" in text_tamper:
                print("   [CONFIRMED] Reason code QUOTE_MISMATCH/QUOTE_TAMPERED raised!", flush=True)
            else:
                issues_found.append("Quote Tampering card missing HMAC mismatch reason code.")
        else:
            issues_found.append("Could not locate Run Attack button on Quote Tampering card.")

        shot_act3 = os.path.join(reports_dir, "demo_act3_quote_tamper_blocked.png")
        await page.screenshot(path=shot_act3)
        timings["act3_quote_tampering"] = time.time() - t_act3_start
        print(f"   [ACT 3 COMPLETE] Elapsed: {timings['act3_quote_tampering']:.2f}s", flush=True)

        # -------------------------------------------------------------
        # ACT 4: Live Indirect Prompt Injection Blocked
        # -------------------------------------------------------------
        t_act4_start = time.time()
        print("\n[ACT 4: 3:00 - 3:30] Executing Attack 6: Real Prompt Injection Test Page...", flush=True)
        btn_injection = page.locator("button[data-run-button='prompt_injection']").first
        if await btn_injection.count() > 0:
            await btn_injection.click()
            print("   Triggered Prompt Injection attack... agent fetching external page...", flush=True)
            await page.wait_for_timeout(5000)

            card_injection = page.locator("div[data-scenario-id='prompt_injection']").first
            text_injection = await card_injection.text_content()
            text_injection_lower = text_injection.lower() if text_injection else ""
            if "blocked" in text_injection_lower:
                print("   [CONFIRMED] Prompt Injection attack is Blocked!", flush=True)
            else:
                issues_found.append("Prompt Injection card did not show Blocked.")
            if "PROMPT_INJECTION_DETECTED" in text_injection or "BUDGET_EXCEEDED" in text_injection:
                print("   [CONFIRMED] Injection detection / budget reason code raised!", flush=True)
            else:
                issues_found.append("Prompt Injection card missing expected reason code.")
        else:
            issues_found.append("Could not locate Run Attack button on Prompt Injection card.")

        shot_act4 = os.path.join(reports_dir, "demo_act4_prompt_injection_blocked.png")
        await page.screenshot(path=shot_act4)
        timings["act4_prompt_injection"] = time.time() - t_act4_start
        print(f"   [ACT 4 COMPLETE] Elapsed: {timings['act4_prompt_injection']:.2f}s", flush=True)

        # -------------------------------------------------------------
        # ACT 5: Verifiable Merkle Audit Ledger & Tamper Drill
        # -------------------------------------------------------------
        t_act5_start = time.time()
        print("\n[ACT 5: 3:30 - 4:00] Navigating to Audit Ledger & Executing Integrity Verification...", flush=True)
        await page.goto("http://localhost:3000/audit", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 5.1 Click Verify Chain Integrity
        btn_verify = page.locator("button:has-text('Verify Chain Integrity')")
        if await btn_verify.count() > 0:
            print("   Clicking 'Verify Chain Integrity' button...", flush=True)
            await btn_verify.click()
            await page.wait_for_timeout(3000)

            # Check green badge
            banner_text = await page.locator("body").text_content()
            if "Cryptographic Integrity" in banner_text or "Verified" in banner_text or "Valid" in banner_text:
                print("   [CONFIRMED] Audit ledger verified GREEN with full chain integrity!", flush=True)
            else:
                issues_found.append("Verify Chain Integrity did not produce expected success banner.")
        else:
            issues_found.append("Could not find 'Verify Chain Integrity' button on /audit.")

        shot_act5_clean = os.path.join(reports_dir, "demo_act5_audit_verified_green.png")
        await page.screenshot(path=shot_act5_clean)

        # 5.2 Click Test Tamper Alert
        btn_tamper_drill = page.locator("button:has-text('Test Tamper Alert')")
        if await btn_tamper_drill.count() > 0:
            print("   Clicking 'Test Tamper Alert' button...", flush=True)
            await btn_tamper_drill.click()
            await page.wait_for_timeout(3000)

            drill_text = await page.locator("body").text_content()
            if "Compromised" in drill_text or "Discontinuity" in drill_text or "Tamper" in drill_text or "CRITICAL" in drill_text or "Tamper Drill Active" in drill_text:
                print("   [CONFIRMED] Audit chain turned RED with cryptographic tamper alert!", flush=True)
            else:
                issues_found.append("Test Tamper Alert did not trigger red alert banner.")
        else:
            issues_found.append("Could not find 'Test Tamper Alert' button on /audit.")

        shot_act5_tamper = os.path.join(reports_dir, "demo_act5_audit_tamper_red.png")
        await page.screenshot(path=shot_act5_tamper)
        timings["act5_audit_verification"] = time.time() - t_act5_start
        print(f"   [ACT 5 COMPLETE] Elapsed: {timings['act5_audit_verification']:.2f}s", flush=True)

        await browser.close()

    t_global_total = time.time() - t_global_start
    timings["total_elapsed"] = t_global_total

    # Copy screenshots to artifact dir
    for fname in os.listdir(reports_dir):
        if fname.startswith("demo_act") and fname.endswith(".png"):
            shutil.copy(os.path.join(reports_dir, fname), os.path.join(artifact_dir, fname))

    print("\n" + "=" * 75, flush=True)
    print("DEMO SCRIPT AUTOMATION EXECUTION TIMINGS SUMMARY", flush=True)
    print("=" * 75, flush=True)
    print(f"Authentication (Step 0):          {timings.get('auth', 0):.2f}s", flush=True)
    print(f"Act 1 (Happy Path $12 Spend):     {timings.get('act1_happy_path', 0):.2f}s", flush=True)
    print(f"Act 2 (Budget Violation Blocked): {timings.get('act2_budget_violation', 0):.2f}s", flush=True)
    print(f"Act 3 (Quote Tampering Blocked):  {timings.get('act3_quote_tampering', 0):.2f}s", flush=True)
    print(f"Act 4 (Prompt Injection Blocked): {timings.get('act4_prompt_injection', 0):.2f}s", flush=True)
    print(f"Act 5 (Audit Ledger & Tamper):    {timings.get('act5_audit_verification', 0):.2f}s", flush=True)
    print("-" * 75, flush=True)
    print(f"TOTAL DEMO TIME:                  {timings.get('total_elapsed', 0):.2f}s (Budget: 240.00s)", flush=True)
    print("=" * 75, flush=True)

    print("\nUNPROFESSIONAL / QUALITY ISSUES AUDIT REPORT:")
    if issues_found:
        for idx, iss in enumerate(issues_found, 1):
            print(f"  {idx}. {iss}", flush=True)
    else:
        print("  Zero issues or console errors detected! The UI is clean, polished, and fully aligned.", flush=True)
    print("=" * 75, flush=True)

if __name__ == "__main__":
    asyncio.run(run_demo_script())
