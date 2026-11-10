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

from supabase import create_client

sb_url = os.getenv("SUPABASE_URL")
sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(sb_url, sb_key)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

from app.security.payload_hash import compute_transaction_payload_hash
from app.services.agents import ensure_user_agent
from app.security.agent_keys import agent_key_manager

def log_step(title: str):
    print(f"\n{'='*75}\n>>> {title}\n{'='*75}")

async def run_cancellation_verification():
    log_step("PHASE 5 VERIFICATION: (3) Cancel at PayPal Checkout Flow")
    
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
                "title": "Phase 5 Checkout Cancellation Test Task",
                "description": "Verifying transaction is never marked Paid when buyer cancels at checkout",
                "budget_max": 50.00,
                "currency": "USD",
                "auto_approve_threshold": 5.00,
                "single_tx_limit": 50.00,
                "allowed_domains": ["127.0.0.1", "localhost", "marketpulse.io"]
            }
        )
        assert t_resp.status_code == 201
        task_id = t_resp.json()["task"]["id"]
    
    # 3. Request quote
    with httpx.Client(timeout=15.0) as client:
        q_resp = client.post(
            f"{VENDOR_GATEWAY_URL}/quote",
            json={
                "task_id": task_id,
                "service_category": "competitor_analysis",
                "service_name": "Standard Market Pricing Scan",
                "scope_details": "cancellation test",
                "tier": "standard",
                "units": 1
            }
        )
        assert q_resp.status_code == 201
        quote_raw = q_resp.json()
    
    # 4. Propose $12.00
    amount = 12.00
    hmac_secret = os.getenv("QUOTE_HMAC_SECRET", "super-secret-hmac-key-nirbhar-2026")
    exp_iso = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    quote_id = f"QTE-CANCEL-{int(datetime.now().timestamp())}"
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
        "justification": "Procuring competitive research (cancellation test).",
        "quote_details": quote_details
    }
    agent_sig = agent_key_manager.sign_proposal(role="service", payload=prop_payload)
    
    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=15.0) as client:
        p_resp = client.post("/transactions/propose", json={"proposal": prop_payload, "signature": agent_sig})
        assert p_resp.status_code == 201
        tx_id = p_resp.json()["transaction"]["id"]
        
        # Approve transaction
        appr_resp = client.post(f"/transactions/{tx_id}/approve", json={"notes": "Approved for checkout cancellation test"})
        assert appr_resp.status_code == 200
        
        # Create PayPal Order
        order_resp = client.post(f"/transactions/{tx_id}/create-paypal-order")
        assert order_resp.status_code == 201
        order_json = order_resp.json()
        paypal_order_id = order_json["paypal_order_id"]
        approval_url = order_json["approval_url"]
        print(f"PayPal Sandbox Order ID: {paypal_order_id}")
        print(f"Approval URL: {approval_url}")

    # 5. Playwright: Navigate to PayPal checkout and click 'Cancel and return to Nirbhar AI'
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        )
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        print("Opening PayPal checkout URL in Playwright...")
        await page.goto(approval_url, wait_until="networkidle", timeout=45000)
        
        print("Looking for 'Cancel and return to Nirbhar AI' link...")
        cancel_link = page.get_by_text("Cancel and return to Nirbhar AI")
        if not await cancel_link.count():
            cancel_link = page.locator("a:has-text('Cancel')")
        
        assert await cancel_link.count() > 0, "Cancel link not found on PayPal page!"
        print("Clicking cancel link...")
        async with page.expect_navigation(wait_until="networkidle", timeout=30000):
            await cancel_link.first.click()
            
        print("Redirected to:", page.url)
        assert "status=cancelled" in page.url
        assert tx_id in page.url
        
        # Capture screenshot of the Payment Result page showing Cancelled
        screenshot_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports", "phase5_cancelled_checkout.png"))
        await page.screenshot(path=screenshot_path)
        print(f"Captured cancelled screenshot at: {screenshot_path}")
        await browser.close()

    # 6. Authoritative Database & API verification: Transaction is NEVER marked Paid
    with httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=15.0) as client:
        status_resp = client.get(f"/transactions/{tx_id}/payment-status")
        assert status_resp.status_code == 200
        st_data = status_resp.json()
        print(f"Payment Status Response: status={st_data['status']}, is_paid={st_data['is_paid']}")
        assert st_data["is_paid"] is False, "CRITICAL ERROR: Cancelled transaction was marked as paid!"
        assert st_data["status"] != "COMPLETED", "CRITICAL ERROR: Status is COMPLETED!"

    # Supabase row check
    tx_db = supabase.table("transactions").select("*").eq("id", tx_id).execute().data[0]
    print(f"Supabase Transaction Status: {tx_db['status']}")
    assert tx_db["status"] != "COMPLETED"
    
    order_db = supabase.table("paypal_orders").select("*").eq("paypal_order_id", paypal_order_id).execute().data[0]
    print(f"PayPal Order Status: {order_db['status']}, Capture ID: {order_db.get('paypal_capture_id')}")
    assert order_db.get("paypal_capture_id") is None
    assert order_db["status"] != "COMPLETED"

    print("\nSUCCESS: Verification (3) fully PASSED! Cancel at checkout leaves transaction unpaid.")
    return {
        "transaction_id": tx_id,
        "paypal_order_id": paypal_order_id,
        "is_paid": False,
        "transaction_status": tx_db["status"],
        "paypal_order_status": order_db["status"],
        "screenshot": screenshot_path
    }

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_cancellation_verification())

