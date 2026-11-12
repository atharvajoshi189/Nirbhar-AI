import asyncio
import json
import os
import subprocess
import time
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".chrome_user_data"))

async def setup_session_and_audit():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    # 1. Launch Chrome with debugging port
    debug_port = 9222
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox"
    ]
    proc = subprocess.Popen(cmd)
    time.sleep(2)

    try:
        # 2. Login via Playwright
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            print("Logging in to set authenticated session...")
            await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            email_btn = page.locator("button:has-text('Continue with Email')")
            if await email_btn.count() > 0:
                await email_btn.click()
                await page.fill("input#login-email", "user_a_nirbhar@test.com")
                await page.fill("input#login-password", "NirbharSecurePass2026!")
                await page.click("button:has-text('Sign In')")
                await page.wait_for_timeout(3000)
            print("Session established successfully!")
            await browser.close()

        # 3. Run Lighthouse CLI on the active debugging port
        routes = {
            "Dashboard": "http://localhost:3000/",
            "New Task": "http://localhost:3000/tasks/new",
            "Trust Review": "http://localhost:3000/tasks/cf12314b-7866-48d0-ac13-bc7f9cf5714d",
            "Audit Log": "http://localhost:3000/audit"
        }

        results = {}

        for name, url in routes.items():
            print(f"\n--- Running Lighthouse Audit for {name} ({url}) ---")
            safe_name = name.lower().replace(" ", "_")
            out_file = os.path.join(REPORTS_DIR, f"lighthouse_{safe_name}.json")

            lh_cmd = [
                "npx", "--yes", "lighthouse",
                url,
                f"--port={debug_port}",
                "--output=json",
                f"--output-path={out_file}",
                "--quiet",
                "--only-categories=performance,accessibility,best-practices,seo",
                "--throttling.cpuSlowdownMultiplier=1"
            ]

            lh_proc = subprocess.run(
                " ".join(lh_cmd),
                shell=True,
                capture_output=True,
                text=True
            )

            if os.path.exists(out_file):
                with open(out_file, "r", encoding="utf-8") as f:
                    lh_data = json.load(f)
                    categories = lh_data.get("categories", {})
                    perf = round((categories.get("performance", {}).get("score") or 0) * 100)
                    a11y = round((categories.get("accessibility", {}).get("score") or 0) * 100)
                    bp = round((categories.get("best-practices", {}).get("score") or 0) * 100)
                    seo = round((categories.get("seo", {}).get("score") or 0) * 100)
                    results[name] = {
                        "url": url,
                        "performance": perf,
                        "accessibility": a11y,
                        "best_practices": bp,
                        "seo": seo
                    }
                    print(f"Results for {name}: Performance={perf}, Accessibility={a11y}, Best Practices={bp}, SEO={seo}")
            else:
                print(f"Failed to generate audit for {name}. Output: {lh_proc.stderr[:300]}")

        print("\n=== FINAL LIGHTHOUSE SUMMARY ===")
        print(json.dumps(results, indent=2))

        # Save summary
        with open(os.path.join(REPORTS_DIR, "lighthouse_summary.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(setup_session_and_audit())

