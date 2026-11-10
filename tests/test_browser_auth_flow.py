import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    os.makedirs("reports", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True
        )
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Unauthenticated visit to root /
        print("Visiting http://localhost:3000/ while logged out...")
        await page.goto("http://localhost:3000/", wait_until="networkidle")
        current_url = page.url
        print(f"Current URL after navigation: {current_url}")

        assert "/login" in current_url, f"Expected redirect to /login, but stayed at {current_url}"
        redirect_screenshot = os.path.abspath("reports/protected_route_redirect.png")
        await page.screenshot(path=redirect_screenshot)
        print(f"Captured protected route redirect screenshot at: {redirect_screenshot}")

        # 2. Enter email and password
        print("Signing in through browser UI as real Supabase user: user_a_nirbhar@test.com...")
        await page.click("text=Continue with Email")
        await page.fill("input[type='email']", "user_a_nirbhar@test.com")
        await page.fill("input[type='password']", "NirbharSecurePass2026!")
        await page.click("button:has-text('Sign In')")
        
        # Wait for redirect to dashboard
        await page.wait_for_url("http://localhost:3000/", timeout=10000)
        print(f"Successfully authenticated! Current URL: {page.url}")

        logged_in_screenshot = os.path.abspath("reports/logged_in_dashboard.png")
        await page.screenshot(path=logged_in_screenshot)
        print(f"Captured authenticated dashboard screenshot at: {logged_in_screenshot}")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
