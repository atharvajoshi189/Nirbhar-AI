import asyncio
import os
import shutil
from playwright.async_api import async_playwright

async def run_tamper_verification():
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

        # 1. Login
        print("Authenticating session...")
        await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        email_btn = page.locator("button:has-text('Continue with Email')")
        if await email_btn.count() > 0:
            await email_btn.click()
            await page.fill("input#login-email", "user_a_nirbhar@test.com")
            await page.fill("input#login-password", "NirbharSecurePass2026!")
            await page.click("button:has-text('Sign In')")
            await page.wait_for_timeout(3500)

        # 2. Audit Log Page
        print("Navigating to /audit...")
        await page.goto("http://localhost:3000/audit", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # 3. Click Test Tamper Alert button
        tamper_btn = page.locator("button:has-text('Test Tamper Alert')")
        print("Clicking 'Test Tamper Alert' button...")
        await tamper_btn.click()

        # 4. Wait for RED Tamper Alert banner to appear
        print("Awaiting RED Tamper Alert banner in UI...")
        tamper_banner = page.locator("text=Audit Chain Tampering Detected!")
        await tamper_banner.wait_for(state="visible", timeout=15000)
        await page.wait_for_timeout(2000)

        # Screenshot the RED Tamper Alert
        shot_path = os.path.join(reports_dir, "phase6_audit_tamper_detected.png")
        await page.screenshot(path=shot_path, full_page=False)
        shutil.copyfile(shot_path, os.path.join(artifact_dir, "phase6_audit_tamper_detected.png"))
        print(f"Captured red tamper banner screenshot: {shot_path}")

        # 5. Click Verify Chain Integrity to prove it recovers back to green
        print("Clicking 'Verify Chain Integrity' to prove clean recovery...")
        clean_btn = page.locator("button:has-text('Verify Chain Integrity')")
        await clean_btn.click()
        await page.wait_for_selector("text=Cryptographic Audit Chain Intact", timeout=15000)
        await page.wait_for_timeout(1500)
        print("Clean verification confirmed!")

        await browser.close()
        print("Tamper verification test completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tamper_verification())
