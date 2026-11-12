import asyncio
import os
import shutil
import json
from playwright.async_api import async_playwright

async def capture_responsive():
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    artifact_dir = r"C:\Users\Gauri Gotmare\.gemini\antigravity\brain\625a4030-a1db-4934-b238-1123f9268d00"
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(artifact_dir, exist_ok=True)

    viewports = [
        {"name": "1440px", "width": 1440, "height": 900},
        {"name": "390px", "width": 390, "height": 844}
    ]

    routes = [
        {"id": "dashboard", "path": "/"},
        {"id": "new_task", "path": "/tasks/new"},
        {"id": "trust_review", "path": "/tasks/cf12314b-7866-48d0-ac13-bc7f9cf5714d"},
        {"id": "transactions", "path": "/transactions"},
        {"id": "audit_log", "path": "/audit"},
        {"id": "not_found", "path": "/non-existent-route"}
    ]

    layout_issues = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )

        for vp in viewports:
            vp_name = vp["name"]
            print(f"\n================ VIEWPORT: {vp_name} ({vp['width']}x{vp['height']}) ================")
            context = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = await context.new_page()

            # Login
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

            for r in routes:
                url = f"http://localhost:3000{r['path']}"
                print(f"Capturing {r['id']} at {vp_name} -> {url}")
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    pass
                await page.wait_for_timeout(2500)

                # Layout validation: check horizontal overflow
                overflow = await page.evaluate("() => document.body.scrollWidth > window.innerWidth")
                scroll_width = await page.evaluate("() => document.body.scrollWidth")
                inner_width = await page.evaluate("() => window.innerWidth")

                if overflow and scroll_width - inner_width > 5:
                    issue = f"Horizontal overflow detected on {r['id']} at {vp_name}: scrollWidth={scroll_width}px > innerWidth={inner_width}px"
                    print(f"  [LAYOUT ISSUE] {issue}")
                    layout_issues.append(issue)
                else:
                    print(f"  [OK] No horizontal overflow on {r['id']} at {vp_name} ({inner_width}px)")

                file_name = f"phase6_{r['id']}_{vp_name}.png"
                out_path = os.path.join(reports_dir, file_name)
                await page.screenshot(path=out_path, full_page=True)
                shutil.copyfile(out_path, os.path.join(artifact_dir, file_name))
                print(f"  Saved screenshot: {file_name}")

            await context.close()

        await browser.close()

    print("\n=== RESPONSIVE LAYOUT AUDIT SUMMARY ===")
    print(f"Total layout issues found: {len(layout_issues)}")
    with open(os.path.join(reports_dir, "responsive_layout_issues.json"), "w", encoding="utf-8") as f:
        json.dump({"issues": layout_issues}, f, indent=2)

if __name__ == "__main__":
    asyncio.run(capture_responsive())

