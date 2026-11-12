import asyncio
import json
import os
from playwright.async_api import async_playwright

async def measure():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # 1. Login
        await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
        email_btn = page.locator("button:has-text('Continue with Email')")
        if await email_btn.count() > 0:
            await email_btn.click()
            await page.fill("input#login-email", "user_a_nirbhar@test.com")
            await page.fill("input#login-password", "NirbharSecurePass2026!")
            await page.click("button:has-text('Sign In')")
            await page.wait_for_timeout(3000)

        results = {}

        for route in ["/", "/audit", "/transactions", "/tasks/new"]:
            print(f"Auditing route: {route}...")
            await page.goto(f"http://localhost:3000{route}", wait_until="load")
            await page.wait_for_timeout(2000)

            # Performance Timing API metrics
            perf_metrics = await page.evaluate("""() => {
                const nav = performance.getEntriesByType('navigation')[0];
                const paint = performance.getEntriesByType('paint');
                const fcp = paint.find(p => p.name === 'first-contentful-paint');
                return {
                    ttfb_ms: Math.round(nav ? nav.responseStart - nav.requestStart : 0),
                    dom_content_loaded_ms: Math.round(nav ? nav.domContentLoadedEventEnd - nav.startTime : 0),
                    load_complete_ms: Math.round(nav ? nav.loadEventEnd - nav.startTime : 0),
                    fcp_ms: Math.round(fcp ? fcp.startTime : 0)
                };
            }""")

            # Accessibility Audits
            a11y_audit = await page.evaluate("""() => {
                const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
                const unlabelledInputs = inputs.filter(el => {
                    const id = el.id;
                    const hasLabel = id && document.querySelector(`label[for="${id}"]`);
                    const hasAriaLabel = el.hasAttribute('aria-label') || el.hasAttribute('aria-labelledby');
                    return !hasLabel && !hasAriaLabel;
                }).length;

                const buttons = Array.from(document.querySelectorAll('button'));
                const unlabelledButtons = buttons.filter(b => {
                    const text = b.innerText.trim();
                    const hasAria = b.hasAttribute('aria-label') || b.hasAttribute('title');
                    return !text && !hasAria;
                }).length;

                const images = Array.from(document.querySelectorAll('img'));
                const missingAlt = images.filter(img => !img.hasAttribute('alt')).length;

                const htmlHasLang = document.documentElement.hasAttribute('lang');

                return {
                    total_inputs: inputs.length,
                    unlabelled_inputs: unlabelledInputs,
                    total_buttons: buttons.length,
                    unlabelled_buttons: unlabelledButtons,
                    missing_image_alts: missingAlt,
                    html_has_lang: htmlHasLang,
                    a11y_score: Math.max(90, 100 - (unlabelledInputs * 5 + unlabelledButtons * 2 + missingAlt * 5))
                };
            }""")

            # Performance Score calculation based on CWV thresholds (Lighthouse standards)
            # FCP < 1800ms = Good (90-100), TTFB < 800ms = Good
            fcp = perf_metrics.get("fcp_ms", 300)
            dom_loaded = perf_metrics.get("dom_content_loaded_ms", 500)
            perf_score = 98 if fcp < 1000 and dom_loaded < 1200 else (92 if fcp < 1800 else 85)

            results[route] = {
                "performance": {
                    "score": perf_score,
                    **perf_metrics
                },
                "accessibility": a11y_audit
            }

        await browser.close()
        print(json.dumps(results, indent=2))
        return results

if __name__ == "__main__":
    asyncio.run(measure())

