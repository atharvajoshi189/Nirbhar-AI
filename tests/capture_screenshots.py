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
        
        # 1. Desktop 1440x900
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto("http://localhost:3000", wait_until="networkidle")
        await asyncio.sleep(1) # allow client health fetch to complete
        desktop_path = os.path.abspath("reports/app-shell-1440px.png")
        await page.screenshot(path=desktop_path, full_page=True)
        print(f"Captured 1440px screenshot at: {desktop_path}")
        
        # Check elements
        nav_items = await page.locator("aside nav a").all_text_contents()
        print(f"Sidebar items found: {[item.strip() for item in nav_items]}")
        
        footer_text = await page.locator("footer").text_content()
        print(f"Footer content: {footer_text.strip() if footer_text else ''}")
        
        await page.close()
        
        # 2. Mobile 390x844 (iPhone 12/13/14 viewport)
        page_mobile = await browser.new_page(viewport={"width": 390, "height": 844})
        await page_mobile.goto("http://localhost:3000", wait_until="networkidle")
        await asyncio.sleep(1)
        mobile_path = os.path.abspath("reports/app-shell-390px.png")
        await page_mobile.screenshot(path=mobile_path, full_page=True)
        print(f"Captured 390px screenshot at: {mobile_path}")
        await page_mobile.close()
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

