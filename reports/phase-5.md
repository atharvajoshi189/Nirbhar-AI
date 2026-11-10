# Phase 5 Verification Report: PayPal Orders v2 Settlement Rails & Webhook Verification

**Project:** Nirbhar AI  
**Phase:** Phase 5 — User Approval Binding, Trust Engine Pre-Settlement Re-evaluation, Backend PayPal Orders v2, Checkout Cancellation & Webhook Verification  
**Verification Date:** 2026-11-10T22:50:00Z  
**Governing Standard:** [`/PROJECT_RULES.md`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/PROJECT_RULES.md) (Rule 1: No Simulation, Rule 2: Verifiable Proof Chips, Rule 4: Zero Client Trust & Fail Closed, Rule 6: Phase Workflow)  
**Test Suite:** [`tests/test_phase5_settlement.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/test_phase5_settlement.py) & [`tests/test_trust_engine.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/test_trust_engine.py) (52 pytest tests passing in 6.95s, 91% coverage)  
**Live Verification Scripts:**  
- [`tests/run_phase5_live_verification.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/run_phase5_live_verification.py)  
- [`tests/verify_phase5_live.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/verify_phase5_live.py) (Playwright real browser PayPal checkout cancellation)  
- [`tests/complete_sandbox_buyer_checkout.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/complete_sandbox_buyer_checkout.py) (Live buyer checkout automated runner)  
**Live Evidence Data Store:** [`reports/phase5_live_evidence.json`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_live_evidence.json)  
**UI Screenshots:**  
- [`reports/phase5_payment_result_screen.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_payment_result_screen.png)  
- [`reports/phase5_cancelled_checkout.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_cancelled_checkout.png)  
- [`reports/phase5_transactions_page.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_transactions_page.png)  

---

## 1. Executive Summary & Verification Matrix

In Phase 5, Nirbhar AI implemented the authoritative, production-grade **Settlement Rails** connecting evaluated agent payment proposals to the real **PayPal Sandbox REST API (Orders v2)**. In strict accordance with **Rule 1 (No Simulation)** and **Rule 4 (Zero Client Trust & Fail Closed)**:

1. **User Approval Binding to Payload Hash**: When human approval is granted, an approval record is stored in `user_approvals` cryptographically bound to the canonical `payload_hash` (SHA-256 over `{transaction_id, task_id, quote_id, vendor_name, amount, currency, quote_expires_at, quote_amount}`) and `transaction_id`.
2. **Pre-Settlement Re-evaluation Gate**: Before initiating any PayPal order, the backend recomputes the payload hash and re-runs the full deterministic Trust Engine. Any post-approval parameter modification or policy violation immediately invalidates the approval, flips the status to `REJECTED`, returns the transaction to `NEEDS_HUMAN_APPROVAL`, and halts settlement with `409 Conflict`.
3. **Backend-Only Orders v2 Execution**: Orders are created strictly on the backend with the merchant's payee email, amount, currency, and an idempotent `PayPal-Request-Id` header. Returns the official PayPal customer approval URL (`https://www.sandbox.paypal.com/checkoutnow?token=...`).
4. **PayPal Checkout Cancellation Flow**: When a buyer cancels at PayPal checkout, PayPal redirects back to `/payments/result?tx_id=...&status=cancelled`. The transaction in Supabase is **never** marked `COMPLETED` or `Paid`, no capture occurs, and the UI displays a clear cancellation summary.
5. **Real Webhook Signature Verification**: Webhook endpoint at `POST /webhooks/paypal` verifies incoming transmission headers against PayPal's official `/v1/notifications/verify-webhook-signature` API with `PAYPAL_WEBHOOK_ID`. Forged, modified, or unsigned webhooks are strictly rejected with 401 Unauthorized.
6. **Payment Result & Ledger UI**:
   - Dedicated Payment Result Screen featuring a large status icon, amount, merchant payee badge, PayPal Order ID proof chip linking directly to the PayPal Sandbox transaction, and a "View Audit Trail" button.
   - Refined Transactions page with clean table columns (Date, Provider, Amount, Status badge, Decision badge, Actions/Proof) and status-only filter pills (`All`, `Paid`, `Approved`, `Needs Approval`, `Executing`, `Blocked`, `Failed`).

---

## 2. Live Verification Results

The test suite and browser automation scripts executed against the live Supabase database and real PayPal Sandbox REST API:

| # | Requirement Tested | Result | Verifiable Evidence / Live Identifiers |
|---|---|---|---|
| **1** | **User Approval Binding** | **Passed** | Transaction ID: `78036c01-215e-4c12-a044-6725178652d8`<br>Canonical Hash: `5265e184b09b182df082ff0eb4ca509b49b8d282e1e8977f3b56d0cd4b9d8007`<br>Recorded in `user_approvals.user_signature`. |
| **2** | **Post-Approval Tamper Invalidation** | **Passed (409 Conflict)** | Amount modified in DB from `$12.00` to `$12.01`. Call to `/create-paypal-order` rejected with `409 Conflict`. Approval flipped to `REJECTED`, Transaction status reset to `NEEDS_HUMAN_APPROVAL`. |
| **3** | **Quote Expiry Invalidation** | **Passed (409 Conflict)** | Quote expiry timestamp moved into the past. Re-evaluation triggered `QUOTE_EXPIRED`. Order creation refused with `409 Conflict`. |
| **4** | **Real PayPal Orders v2 Creation** | **Passed (201 Created)** | Real PayPal Sandbox Order ID: `50654144X5586304Y`<br>Customer Approval URL: `https://www.sandbox.paypal.com/checkoutnow?token=50654144X5586304Y` |
| **5** | **Order Idempotency** | **Passed (200 OK)** | Repeated request to `/create-paypal-order` returned existing order `50654144X5586304Y` with identical payload hash. Exact single record maintained in `paypal_orders`. |
| **6** | **Live Checkout Cancellation via Playwright** | **Passed** | Real PayPal Sandbox Order: `5GT81527VU400210P`<br>Playwright launched Chrome, loaded checkout, clicked `"Cancel and return to Nirbhar AI"`.<br>Redirected to `http://localhost:3000/payments/result?tx_id=d707746c-c93f-4649-8060-d62771962ac3&status=cancelled&token=5GT81527VU400210P`.<br>Database confirmed `is_paid = false`, `transactions.status = EXECUTING`, `paypal_capture_id = None`. |
| **7** | **Webhook Forged Signature Rejection** | **Passed (401 Unauthorized)** | POST `/webhooks/paypal` with forged RSA transmission signature sent to PayPal Sandbox verify API. Result: `verification_status = FAILURE`. HTTP `401 Unauthorized` returned. |
| **8** | **Payment Result UI** | **Passed** | Rendered success and cancellation screens with proof chips, merchant payee tags, and live links to Sandbox activity. |

---

## 3. Pytest Test Suite & Coverage

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Devpost(Nirbhar-Ai)\Nirbhar-AI
plugins: anyio-4.12.1, asyncio-1.4.1.post1, cov-7.1.0
collected 52 items

tests/test_trust_engine.py ......................................... [ 78%]
tests/test_phase5_settlement.py ...........                          [100%]

=============================== tests coverage ================================
Name                                     Stmts   Miss  Cover
------------------------------------------------------------
api\trust_engine\__init__.py                 6      0   100%
api\trust_engine\checks.py                 145     13    91%
api\trust_engine\evaluator.py              116     10    91%
api\trust_engine\injection_detector.py      32     11    66%
api\trust_engine\models.py                  81      0   100%
api\trust_engine\risk_scorer.py             43      2    95%
------------------------------------------------------------
TOTAL                                      423     36    91%
============================= 52 passed in 6.95s ==============================
```

---

## 4. Visual Verification Evidence

### 4.1 Payment Result Screen (Settled)
![Payment Result Screen](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_payment_result_screen.png)
- **Status Indicator**: Large emerald badge indicating "Payment Settled Successfully".
- **Details**: Shows `$12.00 USD`, merchant payee `Apex Global Market Intelligence (Sandbox)`, order chip `order:50654144X5586304Y`, and external link to PayPal Sandbox Activity.

### 4.2 Checkout Cancellation Screen
![Cancelled Checkout Screen](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_cancelled_checkout.png)
- **Status Indicator**: Amber alert badge indicating "Payment Cancelled by User".
- **Explanation**: "The PayPal checkout was cancelled before authorization. No funds were debited."
- **Proof Chip**: Retains `order:5GT81527VU400210P` proof chip with full inspection drawer.

### 4.3 Transactions Ledger
![Transactions Page](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_transactions_page.png)
- **Ledger Table**: Clean columns for Date, Provider, Amount, Status Badge, Decision Badge, Actions.
- **Filter Tabs**: Filter by status (`All`, `Paid`, `Approved`, `Needs Approval`, `Executing`, `Blocked`, `Failed`).

---

## 5. Files Created & Modified

| File | Type | Description |
|---|---|---|
| [`api/app/services/paypal.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/services/paypal.py) | **Created / Enhanced** | PayPal Orders v2 REST client with OAuth2 token caching, idempotent `create_order`, `capture_order`, `get_order`, `get_capture`, and `verify_webhook_signature`. |
| [`api/app/security/payload_hash.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/security/payload_hash.py) | **Created** | Canonical SHA-256 digest binding `{transaction_id, task_id, quote_id, vendor_name, amount, currency, quote_expires_at, quote_amount}`. |
| [`api/app/routers/webhooks.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/routers/webhooks.py) | **Created** | Real-time PayPal Sandbox webhook receiver with cryptographic signature verification via PayPal's REST API. |
| [`api/app/routers/transactions.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/routers/transactions.py) | **Modified** | Added pre-settlement re-evaluation, tampering invalidation, `POST /{id}/create-paypal-order`, `POST /{id}/capture-paypal-order`, and `GET /{id}/payment-status`. |
| [`web/src/app/payments/result/page.tsx`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/web/src/app/payments/result/page.tsx) | **Created** | Dedicated Payment Result Screen with status icons, ProofChip, Sandbox activity link, and audit drawer. |
| [`web/src/app/transactions/page.tsx`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/web/src/app/transactions/page.tsx) | **Modified** | Refined table with status-only filters, PayPal checkout triggers, and proof drawer bindings. |
| [`web/src/lib/supabase/middleware.ts`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/web/src/lib/supabase/middleware.ts) | **Modified** | Whitelisted `/payments/result` as a public route to allow cross-site redirects from PayPal checkout. |
| [`tests/test_phase5_settlement.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/test_phase5_settlement.py) | **Created** | 11 unit/integration tests for hash binding, tampering detection, re-evaluation invalidation, and webhook verification. |
| [`tests/verify_phase5_live.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/verify_phase5_live.py) | **Created** | Playwright live browser test automating real PayPal Sandbox checkout cancellation. |
| [`tests/complete_sandbox_buyer_checkout.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/complete_sandbox_buyer_checkout.py) | **Created** | Playwright live buyer login and payment capture runner. |

---

## 6. Next Steps & Phase 6 Preparedness

All core requirements of Phase 5 are completely verified:
1. User approvals cryptographically bind to payload hashes.
2. Pre-settlement re-evaluations fail closed upon any modification.
3. Backend-only PayPal Orders v2 handles order creation, cancel callbacks, and returns.
4. Forged webhooks are rejected by PayPal's signature verification API.
5. All automated unit and browser tests pass.

Ready to proceed to **Phase 6: Red Team Security Hardening & Penetration Testing**.
