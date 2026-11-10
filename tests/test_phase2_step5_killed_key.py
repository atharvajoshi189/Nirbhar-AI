import os
import re
import sys
import time
import shutil
import subprocess
import httpx
from playwright.sync_api import sync_playwright

USER_A_EMAIL = "user_a_nirbhar@test.com"
PASSWORD = "NirbharSecurePass2026!"
BASE_URL = "http://localhost:3000"
API_URL = "http://127.0.0.1:8000"

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
ENV_BAK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.bak"))

def run_killed_key_verification():
    print("=" * 80)
    print("NIRBHAR AI — STEP 5: KILLED GEMINI KEY ADVERSARIAL VERIFICATION")
    print("=" * 80)

    # 1. Back up .env
    print("\n[Step 1] Backing up .env file...")
    shutil.copyfile(ENV_PATH, ENV_BAK_PATH)
    print(f"  Backup created: {ENV_BAK_PATH}")

    try:
        # 2. Modify .env to kill GEMINI_API_KEY
        print("\n[Step 2] Temporarily poisoning GEMINI_API_KEY in .env...")
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            for line in lines:
                if line.startswith("GEMINI_API_KEY="):
                    f.write("GEMINI_API_KEY=AIzaSy_KILLED_KEY_FOR_PHASE2_VERIFICATION\n")
                else:
                    f.write(line)
        print("  GEMINI_API_KEY set to invalid key in .env")

        # 3. Kill existing backend and ARQ worker
        print("\n[Step 3] Restarting FastAPI server and ARQ worker with poisoned key...")
        subprocess.run(["powershell", "-Command", "Get-Process python | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue"], capture_output=True)
        time.sleep(2)

        # Start FastAPI and ARQ worker as subprocesses
        api_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        arq_proc = subprocess.Popen(
            [sys.executable, "-m", "arq", "app.worker.WorkerSettings"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("  FastAPI and ARQ processes launched with poisoned key. Waiting 4s for startup...")
        time.sleep(4)

        # 4. Check /health endpoint
        print("\n[Step 4] Querying GET /health to verify degraded/error status...")
        health_res = httpx.get(f"{API_URL}/health", timeout=10.0)
        health_data = health_res.json()
        gemini_info = health_data.get("services", {}).get("gemini", {})
        print(f"  Gemini Service Status: {gemini_info.get('status')}")
        print(f"  Gemini Message: {gemini_info.get('message')}")
        assert gemini_info.get("status") == "error", f"Expected error status, got: {gemini_info.get('status')}"

        # 5. Open Real Browser and Create Task
        print("\n[Step 5] Launching Chrome browser and creating task under killed key...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=True
            )
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            # Sign in
            page.goto(f"{BASE_URL}/login")
            page.wait_for_selector('button:has-text("Continue with Email")')
            page.click('button:has-text("Continue with Email")')
            page.fill('input[type="email"]', USER_A_EMAIL)
            page.fill('input[type="password"]', PASSWORD)
            page.click('button:has-text("Sign In")')
            page.wait_for_url(f"{BASE_URL}/", timeout=15000)

            # Create Task
            page.goto(f"{BASE_URL}/tasks/new")
            page.wait_for_selector('text=Create Autonomous Task')
            page.fill('textarea', "Penetration Testing & Security Audit: Audit authentication tokens and API endpoints")
            page.fill('input[inputmode="decimal"]', "45.00")
            page.click('button:has-text("Start Task")')

            # Wait for redirect
            page.wait_for_url(re.compile(r".*/tasks/[a-f0-9-]+"), timeout=20000)
            task_url = page.url
            print(f"  Task created: {task_url}")

            # Wait for Coordinator Agent to attempt execution, fail closed and show FAILED state
            print("  Waiting for agent to fail closed (NO SIMULATED FALLBACK)...")
            page.wait_for_selector('text=FAILED', timeout=30000)
            page.wait_for_selector('text=Execution Failed', timeout=10000)
            time.sleep(1.5)

            failed_screenshot = "reports/phase2_gemini_key_killed_error.png"
            page.screenshot(path=failed_screenshot)
            print(f"  [PASSED] Captured clear error state UI screenshot: {failed_screenshot}")

            # Click Proof Chip to view raw failure in drawer
            print("  Opening raw failure proof drawer...")
            proof_chip = page.locator('button[title="View verifiable proof & raw telemetry"]').first
            proof_chip.click()
            page.wait_for_selector('text=Raw Upstream Payload', timeout=5000)
            time.sleep(1)

            drawer_screenshot = "reports/phase2_gemini_key_killed_drawer.png"
            page.screenshot(path=drawer_screenshot)
            print(f"  [PASSED] Captured failure proof drawer screenshot: {drawer_screenshot}")

            browser.close()

    finally:
        # 6. Restore original .env
        print("\n[Step 6] Restoring genuine .env and restarting healthy services...")
        if os.path.exists(ENV_BAK_PATH):
            shutil.copyfile(ENV_BAK_PATH, ENV_PATH)
            os.remove(ENV_BAK_PATH)
            print("  Restored original .env")

        # Kill test subprocesses
        try:
            api_proc.terminate()
            arq_proc.terminate()
        except Exception:
            pass

        subprocess.run(["powershell", "-Command", "Get-Process python | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue"], capture_output=True)
        time.sleep(2)

        # Restart healthy FastAPI and ARQ processes
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")),
        )
        subprocess.Popen(
            [sys.executable, "-m", "arq", "app.worker.WorkerSettings"],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")),
        )
        time.sleep(4)

        # Verify healthy /health
        health_restored = httpx.get(f"{API_URL}/health", timeout=10.0).json()
        gemini_restored = health_restored.get("services", {}).get("gemini", {}).get("status")
        print(f"  Gemini Restored Status: {gemini_restored}")
        assert gemini_restored == "operational", f"Expected operational, got: {gemini_restored}"
        print("  [PASSED] Health restored to 100% operational!")

    print("\n[PASSED] Requirement 5: Killed Gemini key verified and restored successfully!")

if __name__ == "__main__":
    run_killed_key_verification()
