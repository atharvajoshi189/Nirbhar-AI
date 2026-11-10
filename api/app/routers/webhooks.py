import json
import logging
from typing import Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, status

from app.config import settings
from app.db.supabase import get_supabase_admin_client
from app.services.paypal import paypal_service
from app.services.audit import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/paypal", status_code=status.HTTP_200_OK)
async def paypal_webhook_handler(request: Request):
    """
    PayPal Sandbox Webhook Receiver:
    Rule 1 (No Simulation): Real cryptographic verification via PayPal verify-webhook-signature API.
    Rule 4 (Zero Client Trust & Fail-Closed): Any invalid or missing signature is rejected with 401.
    Processes:
      - PAYMENT.CAPTURE.COMPLETED -> Marks paypal_orders and transactions as COMPLETED
      - PAYMENT.CAPTURE.DENIED / FAILED -> Marks paypal_orders and transactions as FAILED
    """
    body_bytes = await request.body()
    try:
        event = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        logger.error(f"Malformed webhook JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers = dict(request.headers)

    # 1. Real PayPal Webhook Signature Verification
    is_valid, v_status, details = await paypal_service.verify_webhook_signature(headers, event)

    if not is_valid:
        logger.warning(f"PayPal webhook signature verification failed: {v_status}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"PayPal webhook signature verification failed: {v_status}"
        )

    # 2. Process Verified Event
    event_type = event.get("event_type")
    event_id = event.get("id")
    resource = event.get("resource", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase = get_supabase_admin_client()

    logger.info(f"Verified PayPal webhook received: {event_type} (Event ID: {event_id})")

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        capture_id = resource.get("id")
        related_ids = resource.get("supplementary_data", {}).get("related_ids", {})
        order_id = related_ids.get("order_id")

        # Find matching order in paypal_orders
        query = supabase.table("paypal_orders").select("*")
        if order_id:
            query = query.eq("paypal_order_id", order_id)
        elif capture_id:
            query = query.eq("paypal_capture_id", capture_id)

        matched_orders = query.execute().data
        if matched_orders:
            order_rec = matched_orders[0]
            tx_id = order_rec["transaction_id"]
            user_id = order_rec["user_id"]
            task_id = order_rec["task_id"]

            # Update paypal_orders
            supabase.table("paypal_orders").update({
                "paypal_capture_id": capture_id,
                "status": "COMPLETED",
                "raw_capture_payload": resource,
                "updated_at": now_iso
            }).eq("id", order_rec["id"]).execute()

            # Update transactions
            supabase.table("transactions").update({
                "status": "COMPLETED",
                "updated_at": now_iso
            }).eq("id", tx_id).execute()

            # Log immutable audit event
            audit_service.append_event(
                user_id=user_id,
                event_type="PAYMENT_CONFIRMED_VIA_VERIFIED_WEBHOOK",
                task_id=task_id,
                transaction_id=tx_id,
                payload={
                    "event_id": event_id,
                    "event_type": event_type,
                    "paypal_order_id": order_rec["paypal_order_id"],
                    "paypal_capture_id": capture_id,
                    "amount": resource.get("amount", {}).get("value"),
                    "currency": resource.get("amount", {}).get("currency_code"),
                    "verified": True
                }
            )

        return {"status": "success", "event_type": event_type, "processed": bool(matched_orders)}

    elif event_type in ("PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.DECLINED", "PAYMENT.CAPTURE.FAILED"):
        capture_id = resource.get("id")
        related_ids = resource.get("supplementary_data", {}).get("related_ids", {})
        order_id = related_ids.get("order_id")

        query = supabase.table("paypal_orders").select("*")
        if order_id:
            query = query.eq("paypal_order_id", order_id)
        elif capture_id:
            query = query.eq("paypal_capture_id", capture_id)

        matched_orders = query.execute().data
        if matched_orders:
            order_rec = matched_orders[0]
            tx_id = order_rec["transaction_id"]
            user_id = order_rec["user_id"]
            task_id = order_rec["task_id"]

            supabase.table("paypal_orders").update({
                "status": "FAILED",
                "raw_capture_payload": resource,
                "updated_at": now_iso
            }).eq("id", order_rec["id"]).execute()

            supabase.table("transactions").update({
                "status": "FAILED",
                "updated_at": now_iso
            }).eq("id", tx_id).execute()

            audit_service.append_event(
                user_id=user_id,
                event_type="PAYMENT_FAILED_VIA_VERIFIED_WEBHOOK",
                task_id=task_id,
                transaction_id=tx_id,
                payload={
                    "event_id": event_id,
                    "event_type": event_type,
                    "paypal_order_id": order_rec["paypal_order_id"],
                    "status": "FAILED"
                }
            )

        return {"status": "failed_recorded", "event_type": event_type}

    return {"status": "ignored", "event_type": event_type}
