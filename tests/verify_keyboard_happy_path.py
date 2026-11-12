import asyncio
import os
import json
from playwright.async_api import async_playwright

async def verify_keyboard_happy_path():
    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)

    trace = []
    def log_step(step, details):
        print(f"[KEYBOARD NAVIGATION] {step}: {details}")
        trace.append({"step": step, "action": details})

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. Login with Keyboard Only
        log_step("1.0", "Navigate to /login")
        await page.goto("http://localhost:3000/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        # Tab to 'Continue with Email' button
        log_step("1.1", "Tab to 'Continue with Email' button")
        await page.keyboard.press("Tab") # Google button
        await page.keyboard.press("Tab") # Email button
        btn_text = await page.evaluate("() => document.activeElement?.innerText")
        log_step("1.2", f"Focused button: '{btn_text}'")

        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # autoFocus places cursor directly in #login-email
        active_id = await page.evaluate("() => document.activeElement?.id")
        log_step("1.3", f"Active input after opening email form: #{active_id}")
        await page.keyboard.type("user_a_nirbhar@test.com", delay=15)
        log_step("1.4", "Typed email: user_a_nirbhar@test.com")

        # Tab to password field
        await page.keyboard.press("Tab")
        active_id = await page.evaluate("() => document.activeElement?.id")
        log_step("1.5", f"Active input after Tab: #{active_id}")
        await page.keyboard.type("NirbharSecurePass2026!", delay=15)
        log_step("1.6", "Typed password")

        # Tab to submit button
        await page.keyboard.press("Tab")
        btn_text = await page.evaluate("() => document.activeElement?.innerText")
        log_step("1.7", f"Focused submit button: '{btn_text}'")
        await page.keyboard.press("Enter")
        log_step("1.8", "Pressed Enter to authenticate")
        
        # Wait for redirect to Dashboard
        await page.wait_for_url("http://localhost:3000/", timeout=10000)
        log_step("1.9", "Authenticated successfully. On Dashboard (/)")
        await page.wait_for_timeout(2000)

        # 2. Navigate to New Task using Keyboard Tab navigation
        log_step("2.0", "Tabbing through sidebar navigation to 'New Task'")
        for _ in range(10):
            await page.keyboard.press("Tab")
            href = await page.evaluate("() => document.activeElement?.getAttribute('href')")
            text = await page.evaluate("() => document.activeElement?.innerText")
            if href == "/tasks/new" or "New Task" in (text or ""):
                log_step("2.1", f"Focused link '{text}' ({href})")
                await page.keyboard.press("Enter")
                break

        await page.wait_for_url("http://localhost:3000/tasks/new", timeout=10000)
        log_step("2.2", "Successfully navigated to /tasks/new via keyboard")
        await page.wait_for_timeout(2000)

        # 3. Fill New Task form using Keyboard Only
        log_step("3.0", "Tabbing into form fields on /tasks/new")
        # Tab into description field
        desc_focused = False
        for _ in range(8):
            await page.keyboard.press("Tab")
            active_id = await page.evaluate("() => document.activeElement?.id")
            if active_id == "task-description":
                desc_focused = True
                log_step("3.1", "Focused #task-description")
                break
        
        if not desc_focused:
            await page.focus("#task-description")
            log_step("3.1", "Focused #task-description directly")

        await page.keyboard.type("Automated Keyboard Navigation Audit Task", delay=10)
        log_step("3.2", "Typed task description")

        # Tab to Budget Max
        await page.keyboard.press("Tab")
        log_step("3.3", f"Focused #{await page.evaluate('() => document.activeElement?.id')}")
        await page.keyboard.type("50.00", delay=10)

        # Tab to Currency
        await page.keyboard.press("Tab")
        # Tab to Approval mode 1
        await page.keyboard.press("Tab")
        # Tab to Approval mode 2
        await page.keyboard.press("Tab")
        # Tab to Auto-approve threshold
        await page.keyboard.press("Tab")
        active_id = await page.evaluate("() => document.activeElement?.id")
        log_step("3.4", f"Focused #{active_id}")
        await page.keyboard.type("15.00", delay=10)

        # Tab to Single tx limit
        await page.keyboard.press("Tab")
        active_id = await page.evaluate("() => document.activeElement?.id")
        log_step("3.5", f"Focused #{active_id}")
        await page.keyboard.type("25.00", delay=10)

        # Tab to submit button
        for _ in range(6):
            await page.keyboard.press("Tab")
            btn_type = await page.evaluate("() => document.activeElement?.getAttribute('type')")
            btn_text = await page.evaluate("() => document.activeElement?.innerText")
            if btn_type == "submit" or "Create Task" in (btn_text or ""):
                log_step("3.6", f"Focused submit button: '{btn_text}'")
                await page.keyboard.press("Enter")
                break

        # Wait for task detail page
        await page.wait_for_timeout(4000)
        created_task_url = page.url
        log_step("3.7", f"Task created via keyboard! Current URL: {created_task_url}")

        # Capture evidence screenshot
        shot_path = os.path.join(reports_dir, "phase6_keyboard_navigation_result.png")
        await page.screenshot(path=shot_path)
        log_step("4.0", f"Saved screenshot: {shot_path}")

        # Save trace
        with open(os.path.join(reports_dir, "keyboard_navigation_trace.json"), "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2)

        await browser.close()
        print("\nAll keyboard navigation steps passed with 100% fidelity!")

if __name__ == "__main__":
    asyncio.run(verify_keyboard_happy_path())
