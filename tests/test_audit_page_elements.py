import asyncio
import os
import shutil
from playwright.async_api import async_playwright

async def run():
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

        # Login
        print("Navigating to login...")
        await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        email_btn = page.locator("button:has-text('Continue with Email')")
        if await email_btn.count() > 0:
            await email_btn.click()
            await page.fill("input#login-email", "user_a_nirbhar@test.com")
            await page.fill("input#login-password", "NirbharSecurePass2026!")
            await page.click("button:has-text('Sign In')")
            await page.wait_for_timeout(3000)

        # Audit page
        print("Navigating to /audit...")
        await page.goto("http://localhost:3000/audit", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Verify Chain button
        verify_btn = page.locator("button:has-text('Verify Chain Integrity')")
        if await verify_btn.count() > 0:
            print("Clicking Verify Chain Integrity...")
            await verify_btn.click()
            await page.wait_for_selector("text=Cryptographic Audit Chain Intact", timeout=15000)
            await page.wait_for_timeout(1500)

        # Capture Audit Log full page screenshot
        audit_path = os.path.join(reports_dir, "phase6_audit_log_page.png")
        await page.screenshot(path=audit_path, full_page=True)
        shutil.copyfile(audit_path, os.path.join(artifact_dir, "phase6_audit_log_page.png"))
        print(f"Captured full audit page screenshot: {audit_path}")

        # Find all buttons with proof or ProofChip
        proof_btns = page.locator("button[title*='proof']")
        count = await proof_btns.count()
        print(f"Found {count} buttons matching title*='proof'")

        if count == 0:
            # Check all buttons
            all_btns = await page.eval_on_selector_all("button", "elements => elements.map(e => e.outerHTML.slice(0, 120))")
            print("Sample buttons on page:", all_btns[:10])
        else:
            # Click first proof chip
            first_chip = proof_btns.first
            await first_chip.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await first_chip.click()
            await page.wait_for_selector("#proof-drawer-title", timeout=10000)
            await page.wait_for_timeout(1500)

            # Screenshot drawer
            drawer_path = os.path.join(reports_dir, "phase6_global_proof_drawer.png")
            await page.screenshot(path=drawer_path)
            shutil.copyfile(drawer_path, os.path.join(artifact_dir, "phase6_global_proof_drawer.png"))
            print(f"Captured global proof drawer screenshot: {drawer_path}")

            # Test keyboard dismiss: Escape
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)

        # Capture 404 page
        print("Navigating to 404 page...")
        try:
            await page.goto("http://localhost:3000/non-existent-route", wait_until="load")
        except Exception as e:
            print(f"Goto 404 notice: {e}")
        await page.wait_for_timeout(2000)
        not_found_path = os.path.join(reports_dir, "phase6_404_page.png")
        await page.screenshot(path=not_found_path)
        shutil.copyfile(not_found_path, os.path.join(artifact_dir, "phase6_404_page.png"))
        print(f"Captured 404 page screenshot: {not_found_path}")

        await browser.close()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(run())

