import os
import sys
import json
import httpx
import hmac
import hashlib
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
VENDOR_GATEWAY_URL = "http://127.0.0.1:8001"
WEB_URL = "http://localhost:3000"
USER_EMAIL = "user_a_nirbhar@test.com"
USER_PASSWORD = "NirbharSecurePass2026!"

PAYPAL_BUYER_EMAIL = os.getenv("PAYPAL_BUYER_EMAIL")
PAYPAL_BUYER_PASSWORD = os.getenv("PAYPAL_BUYER_PASSWORD")

from supabase import create_client

sb_url = os.getenv("SUPABASE_URL")
sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(sb_url, sb_key)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.security.payload_hash import compute_transaction_payload_hash
from app.services.agents import ensure_user_agent
from app.security.agent_keys import agent_key_manager
from app.services.paypal import paypal_service

def log_step(title: str):
    print(f"\n{'='*75}\n>>> {title}\n{'='*75}")

async def run_buyer_checkout():
    log_step("PHASE 5: Live PayPal Sandbox Buyer Checkout & Capture")

    if not PAYPAL_BUYER_EMAIL or not PAYPAL_BUYER_PASSWORD:
        print("\n[ATTENTION REQUIRED]")
        print("Missing PAYPAL_BUYER_EMAIL or PAYPAL_BUYER_PASSWORD.")
        print("Please provide PayPal Sandbox personal buyer credentials from developer.paypal.com")
        return {"status": "AWAITING_BUYER_CREDENTIALS"}

    # 1. Sign in & authenticate
    auth_resp = supabase.auth.sign_in_with_password({"email": USER_EMAIL, "password": USER_PASSWORD})
    user_id = auth_resp.user.id
    token = auth_resp.session.access_token
    auth_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    agent_id = ensure_user_agent(user_id=user_id, role="service")
    pub_key = agent_key_manager.get_public_keys()["service"]
    supabase.table("agents").update({"public_key": pub_key}).eq("id", agent_id).execute()

    # 2. Create Task
    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=15.0) as client:
        t_resp = client.post(
            "/tasks",
            json={
                "title": "Phase 5 Live Settlement Verification Task",
                "description": "Procuring real MarketPulse scan under verified PayPal settlement",
                "budget_max": 50.00,
                "currency": "USD",
                "auto_approve_threshold": 5.00,
                "single_tx_limit": 50.00,
                "allowed_domains": ["127.0.0.1", "localhost", "marketpulse.io"]
            }
        )
        assert t_resp.status_code == 201
        task_id = t_resp.json()["task"]["id"]

    # 3. Dynamic Quote
    with httpx.Client(timeout=15.0) as client:
        q_resp = client.post(
            f"{VENDOR_GATEWAY_URL}/quote",
            json={
                "task_id": task_id,
                "service_category": "competitor_analysis",
                "service_name": "Standard Market Pricing Scan",
                "scope_details": "live buyer checkout verification",
                "tier": "standard",
                "units": 1
            }
        )
        assert q_resp.status_code == 201
        quote_raw = q_resp.json()

    # 4. Propose $12.00
    amount = 12.00
    hmac_secret = os.getenv("QUOTE_HMAC_SECRET", "super-secret-hmac-key-nirbhar-2026")
    exp_iso = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    quote_id = f"QTE-SETTLE-{int(datetime.now().timestamp())}"
    preimage = f"{quote_id}:{quote_raw['merchant_id']}:{quote_raw['payee_email']}:{amount:.2f}:USD:{exp_iso}"
    sig = hmac.new(hmac_secret.encode(), preimage.encode(), hashlib.sha256).hexdigest()

    quote_details = dict(quote_raw)
    quote_details.update({
        "quote_id": quote_id,
        "amount": amount,
        "expires_at": exp_iso,
        "hmac_signature": sig
    })

    prop_payload = {
        "agent_id": agent_id,
        "task_id": task_id,
        "provider": quote_raw["merchant_name"],
        "service": quote_raw["service_name"],
        "amount": amount,
        "currency": "USD",
        "quote_id": quote_id,
        "justification": f"Procuring competitive research from {quote_raw['merchant_name']}.",
        "quote_details": quote_details
    }
    agent_sig = agent_key_manager.sign_proposal(role="service", payload=prop_payload)

    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=15.0) as client:
        p_resp = client.post("/transactions/propose", json={"proposal": prop_payload, "signature": agent_sig})
        assert p_resp.status_code == 201
        tx_id = p_resp.json()["transaction"]["id"]

        # Approve
        appr_resp = client.post(f"/transactions/{tx_id}/approve", json={"notes": "User approved $12.00 live checkout"})
        assert appr_resp.status_code == 200

        # Create Order
        order_resp = client.post(f"/transactions/{tx_id}/create-paypal-order")
        assert order_resp.status_code == 201
        order_data = order_resp.json()
        paypal_order_id = order_data["paypal_order_id"]
        approval_url = order_data["approval_url"]
        print(f"PayPal Sandbox Order ID: {paypal_order_id}")
        print(f"Approval URL: {approval_url}")

    # 5. Playwright Buyer Checkout
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        print(f"Navigating to PayPal Sandbox checkout: {approval_url}")
        await page.goto(approval_url, wait_until="networkidle", timeout=45000)

        # Fill buyer email
        print(f"Entering buyer email: {PAYPAL_BUYER_EMAIL}")
        email_input = page.locator("input[type='email'], input#email, input[name='login_email']")
        await email_input.fill(PAYPAL_BUYER_EMAIL)

        next_btn = page.locator("button#btnNext, button:has-text('Next')")
        if await next_btn.count() > 0:
            await next_btn.first.click()
            await page.wait_for_timeout(2000)

        # Fill buyer password
        print("Entering buyer password...")
        pwd_input = page.locator("input[type='password'], input#password, input[name='login_password']")
        await pwd_input.fill(PAYPAL_BUYER_PASSWORD)

        login_btn = page.locator("button#btnLogin, button:has-text('Log In')")
        await login_btn.first.click()
        print("Logging in to PayPal Sandbox...")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(5000)

        # Click payment / complete purchase button
        pay_btn = page.locator("button#payment-submit-btn, button:has-text('Complete Purchase'), button:has-text('Pay Now'), button:has-text('Continue')")
        if await pay_btn.count() > 0:
            print("Clicking Complete Purchase / Pay Now button...")
            async with page.expect_navigation(wait_until="networkidle", timeout=45000):
                await pay_btn.first.click()

        print("Landed URL after checkout:", page.url)
        # Capture screenshot of result screen
        screenshot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports", "phase5_buyer_checkout_result.png"))
        await page.screenshot(path=screenshot_path)
        await browser.close()

    # 6. Capture on backend
    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=20.0) as client:
        cap_resp = client.post(
            f"/transactions/{tx_id}/capture-paypal-order",
            json={"paypal_order_id": paypal_order_id}
        )
        print("Capture response:", cap_resp.status_code, cap_resp.json())
        assert cap_resp.status_code in (200, 201)
        cap_data = cap_resp.json()
        capture_id = cap_data["paypal_capture_id"]

        # Check payment status
        status_resp = client.get(f"/transactions/{tx_id}/payment-status")
        assert status_resp.status_code == 200
        st_data = status_resp.json()
        assert st_data["is_paid"] is True
        assert st_data["status"] == "COMPLETED"

    # 7. Query PayPal Capture Details from Sandbox REST API
    capture_details = await paypal_service.get_capture(capture_id)
    print("Capture Details from PayPal API:", json.dumps(capture_details, indent=2))

    return {
        "status": "SUCCESS",
        "transaction_id": tx_id,
        "paypal_order_id": paypal_order_id,
        "paypal_capture_id": capture_id,
        "capture_details": capture_details,
        "screenshot": screenshot_path
    }

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_buyer_checkout())
