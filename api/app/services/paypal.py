import os
import time
import logging
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

class PayPalService:
    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.api_base = settings.PAYPAL_API_BASE or "https://api-m.sandbox.paypal.com"
        self.webhook_id = settings.PAYPAL_WEBHOOK_ID
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def get_access_token(self) -> str:
        """Obtains OAuth 2.0 bearer access token using client credentials."""
        now = time.time()
        if self._cached_token and now < (self._token_expires_at - 60):
            return self._cached_token

        if not self.client_id or not self.client_secret:
            raise ValueError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be configured in environment.")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"}
            )
            if resp.status_code != 200:
                logger.error(f"PayPal OAuth failed ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"Failed to authenticate with PayPal: {resp.text}")

            data = resp.json()
            self._cached_token = data["access_token"]
            expires_in = data.get("expires_in", 32400)
            self._token_expires_at = now + expires_in
            return self._cached_token

    async def create_order(
        self,
        transaction_id: str,
        amount: Decimal | float,
        currency: str,
        payee_email: str,
        task_title: str,
        provider_name: str,
        return_url: str,
        cancel_url: str,
        payload_hash: str
    ) -> Dict[str, Any]:
        """
        Creates a PayPal v2 Checkout Order with intent CAPTURE.
        Rule 1: Real PayPal Sandbox REST API call.
        Rule 4: Strictly executed backend-only with idempotency header.
        """
        token = await self.get_access_token()
        amt_str = f"{float(amount):.2f}"

        # Bound idempotency key ensures duplicate requests never create multiple orders
        idempotency_key = f"nirbhar_ord_{transaction_id}_{payload_hash[:12]}"

        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": transaction_id,
                    "description": f"Payment for {task_title[:50]} via {provider_name[:40]}",
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": amt_str
                    },
                    "payee": {
                        "email_address": payee_email
                    }
                }
            ],
            "application_context": {
                "brand_name": "Nirbhar AI",
                "landing_page": "NO_PREFERENCE",
                "user_action": "PAY_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url
            }
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.api_base}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": idempotency_key
                },
                json=order_payload
            )

            if resp.status_code not in (200, 201):
                logger.error(f"PayPal create_order error ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"PayPal order creation failed ({resp.status_code}): {resp.text}")

            data = resp.json()
            order_id = data.get("id")
            order_status = data.get("status", "CREATED")

            approval_url = None
            for link in data.get("links", []):
                if link.get("rel") == "approve":
                    approval_url = link.get("href")
                    break

            return {
                "order_id": order_id,
                "status": order_status,
                "approval_url": approval_url,
                "idempotency_key": idempotency_key,
                "raw": data
            }

    async def capture_order(
        self,
        paypal_order_id: str,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Captures authorized PayPal Order.
        Rule 1: Real PayPal Sandbox REST API call.
        """
        token = await self.get_access_token()
        idempotency_key = f"nirbhar_cap_{paypal_order_id}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{self.api_base}/v2/checkout/orders/{paypal_order_id}/capture",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": idempotency_key
                }
            )

            if resp.status_code not in (200, 201):
                logger.error(f"PayPal capture_order error ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"PayPal capture failed ({resp.status_code}): {resp.text}")

            data = resp.json()
            status = data.get("status", "COMPLETED")

            # Extract capture ID from purchase units
            capture_id = None
            purchase_units = data.get("purchase_units", [])
            if purchase_units:
                payments = purchase_units[0].get("payments", {})
                captures = payments.get("captures", [])
                if captures:
                    capture_id = captures[0].get("id")

            return {
                "order_id": paypal_order_id,
                "capture_id": capture_id,
                "status": status,
                "raw": data
            }

    async def get_order(self, paypal_order_id: str) -> Dict[str, Any]:
        """Retrieves live PayPal Order details."""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.api_base}/v2/checkout/orders/{paypal_order_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch PayPal order ({resp.status_code}): {resp.text}")
            return resp.json()

    async def get_capture(self, capture_id: str) -> Dict[str, Any]:
        """Retrieves live PayPal Capture details from /v2/payments/captures/{id}."""
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.api_base}/v2/payments/captures/{capture_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch PayPal capture ({resp.status_code}): {resp.text}")
            return resp.json()

    async def verify_webhook_signature(
        self,
        headers: Dict[str, str],
        webhook_event: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifies real webhook signature using PayPal Sandbox API:
        POST /v1/notifications/verify-webhook-signature
        Rule 4 (Zero Client Trust & Fail-Closed): Any mismatch or missing header fails verification.
        """
        token = await self.get_access_token()

        auth_algo = headers.get("paypal-auth-algo") or headers.get("PAYPAL-AUTH-ALGO")
        cert_url = headers.get("paypal-cert-url") or headers.get("PAYPAL-CERT-URL")
        transmission_id = headers.get("paypal-transmission-id") or headers.get("PAYPAL-TRANSMISSION-ID")
        transmission_sig = headers.get("paypal-transmission-sig") or headers.get("PAYPAL-TRANSMISSION-SIG")
        transmission_time = headers.get("paypal-transmission-time") or headers.get("PAYPAL-TRANSMISSION-TIME")
        webhook_id = self.webhook_id or os.getenv("PAYPAL_WEBHOOK_ID", "7ED49251RM274261H")

        if not all([auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]):
            return False, "MISSING_REQUIRED_HEADERS", {"error": "Missing PayPal signature headers"}

        payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": webhook_id,
            "webhook_event": webhook_event
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/notifications/verify-webhook-signature",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if resp.status_code != 200:
                logger.error(f"PayPal verify-webhook-signature error ({resp.status_code}): {resp.text}")
                return False, "API_ERROR", resp.json() if resp.headers.get("content-type") == "application/json" else {"raw": resp.text}

            data = resp.json()
            v_status = data.get("verification_status", "FAILURE")
            is_valid = (v_status == "SUCCESS")
            return is_valid, v_status, data

paypal_service = PayPalService()

