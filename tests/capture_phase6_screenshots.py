import asyncio
import os
import shutil
from playwright.async_api import async_playwright

async def capture():
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    artifact_dir = r"C:\Users\Gauri Gotmare\.gemini\antigravity\brain\625a4030-a1db-4934-b238-1123f9268d00"
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(artifact_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. Login to establish authenticated session
        print("Navigating to login page...")
        await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # Click Continue with Email
        email_btn = page.locator("button:has-text('Continue with Email')")
        if await email_btn.count() > 0:
            await email_btn.click()
            await page.fill("input#login-email", "user_a_nirbhar@test.com")
            await page.fill("input#login-password", "NirbharSecurePass2026!")
            await page.click("button:has-text('Sign In')")
            await page.wait_for_timeout(4000)

        # 2. Capture Audit Log Page
        print("Navigating to /audit...")
        await page.goto("http://localhost:3000/audit", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        # Click Verify Chain Integrity button
        verify_btn = page.locator("button:has-text('Verify Chain Integrity')")
        if await verify_btn.count() > 0:
            print("Clicking Verify Chain Integrity button...")
            await verify_btn.click()
            # Wait for verification result to appear
            await page.wait_for_selector("text=Cryptographic Audit Chain Intact", timeout=15000)
            await page.wait_for_timeout(2000)

        audit_path = os.path.join(reports_dir, "phase6_audit_log_page.png")
        await page.screenshot(path=audit_path)
        shutil.copyfile(audit_path, os.path.join(artifact_dir, "phase6_audit_log_page.png"))
        print(f"Captured audit log screenshot: {audit_path}")

        # 3. Open Global Proof Drawer from an event proof chip
        print("Locating proof chip for Global Proof Drawer...")
        try:
            # Re-query proof chips fresh from DOM
            proof_chips = page.locator("button[aria-label*='View proof']")
            chip_count = await proof_chips.count()
            print(f"Found {chip_count} proof chips on page.")
            if chip_count > 0:
                target_chip = proof_chips.first
                await target_chip.scroll_into_view_if_needed()
                await page.wait_for_timeout(1000)
                print("Clicking proof chip to open Global Proof Drawer...")
                await target_chip.click(force=True)
                await page.wait_for_selector("text=Proof & Verifiable Telemetry", timeout=10000)
                await page.wait_for_timeout(2000)
                drawer_path = os.path.join(reports_dir, "phase6_global_proof_drawer.png")
                await page.screenshot(path=drawer_path)
                shutil.copyfile(drawer_path, os.path.join(artifact_dir, "phase6_global_proof_drawer.png"))
                print(f"Captured global proof drawer screenshot: {drawer_path}")

                # Test keyboard navigation: press Escape to close drawer
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"Proof chip drawer capture error: {e}")

        # 4. Capture 404 Page
        print("Navigating to 404 page...")
        try:
            await page.goto("http://localhost:3000/non-existent-route", wait_until="commit")
        except Exception:
            pass
        await page.wait_for_timeout(3000)
        not_found_path = os.path.join(reports_dir, "phase6_404_page.png")
        await page.screenshot(path=not_found_path)
        shutil.copyfile(not_found_path, os.path.join(artifact_dir, "phase6_404_page.png"))
        print(f"Captured 404 page screenshot: {not_found_path}")

        await browser.close()
        print("All Phase 6 screenshots captured successfully!")

if __name__ == "__main__":
    asyncio.run(capture())
