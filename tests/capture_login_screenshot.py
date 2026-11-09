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
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://localhost:3000/login", wait_until="networkidle")
        await asyncio.sleep(1)
        login_path = os.path.abspath("reports/login-page.png")
        await page.screenshot(path=login_path)
        print(f"Captured login screenshot at: {login_path}")

        # Check buttons
        buttons = await page.locator("button").all_text_contents()
        print(f"Buttons found on login page: {[b.strip() for b in buttons]}")

        await page.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
