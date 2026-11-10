# Phase 5 Verification Report: PayPal Orders v2 Settlement Rails & Webhook Verification

**Project:** Nirbhar AI  
**Phase:** Phase 5 — User Approval Binding, Trust Engine Pre-Settlement Re-evaluation, Backend PayPal Orders v2, Webhook Signature Verification & Payment Result UI  
**Verification Date:** 2026-11-10T22:34:00Z  
**Governing Standard:** [`/PROJECT_RULES.md`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/PROJECT_RULES.md) (Rule 1: No Simulation, Rule 2: Verifiable Proof Chips, Rule 4: Zero Client Trust & Fail Closed, Rule 6: Phase Workflow)  
**Test Suite:** [`tests/test_phase5_settlement.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/test_phase5_settlement.py) & [`tests/test_trust_engine.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/test_trust_engine.py) (52 pytest tests passing in 6.37s)  
**Live Verification Script:** [`tests/run_phase5_live_verification.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/run_phase5_live_verification.py)  
**Live Evidence Data Store:** [`reports/phase5_live_evidence.json`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_live_evidence.json)  
**UI Screenshots:**  
- [`reports/phase5_payment_result_screen.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_payment_result_screen.png)  
- [`reports/phase5_transactions_page.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_transactions_page.png)  

---

## 1. Executive Summary & Verification Matrix

In Phase 5, Nirbhar AI established the authoritative, production-grade **Settlement Rails** connecting evaluated agent payment proposals to the real **PayPal Sandbox REST API (Orders v2)**. In accordance with **Rule 1 (No Simulation)** and **Rule 4 (Zero Client Trust & Fail Closed)**:
1. **User Approval Binding to Payload Hash**: When human approval is granted, an approval record is stored in `user_approvals` cryptographically bound to the canonical `payload_hash` and `transaction_id`.
2. **Pre-Settlement Re-evaluation Gate**: Before initiating any PayPal order, the backend recomputes the payload hash and re-runs the full deterministic Trust Engine. Any post-approval parameter modification or policy violation immediately invalidates the approval, flips the status to `REJECTED`, returns the transaction to `NEEDS_HUMAN_APPROVAL`, and halts settlement.
3. **Backend-Only Orders v2 Execution**: Orders are created strictly on the backend with the merchant's payee email, amount, currency, and an idempotent `PayPal-Request-Id` header. Returns the official PayPal customer approval URL (`https://www.sandbox.paypal.com/checkoutnow?token=...`).
4. **PayPal Capture on Return**: Upon checkout return, the backend executes `POST /v2/checkout/orders/{id}/capture`, records `paypal_capture_id`, updates `paypal_orders` and `transactions` to `COMPLETED`, and appends an immutable audit event.
5. **Real Webhook Signature Verification**: Webhook endpoint at `POST /webhooks/paypal` verifies incoming transmission headers against PayPal's official `/v1/notifications/verify-webhook-signature` API with `PAYPAL_WEBHOOK_ID`. Forged or unsigned webhooks are strictly rejected with 401 Unauthorized.
6. **Payment Result & Ledger UI**:
   - Dedicated Payment Result Screen featuring a large status icon, amount, merchant payee badge, PayPal Order ID proof chip linking directly to the PayPal Sandbox transaction, and a "View Audit Trail" button.
   - Refined Transactions page with clean table columns (Date, Provider, Amount, Status badge, Decision badge, Actions/Proof) and status-only filter pills (`All`, `Paid`, `Approved`, `Needs Approval`, `Executing`, `Blocked`, `Failed`).

---

## 2. Live Verification Results

Execution log from the automated end-to-end verification script ([`tests/run_phase5_live_verification.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/run_phase5_live_verification.py)):

| Step | Requirement Tested | Observed Status | Evidence / Return Payload |
|---|---|---|---|
| **1** | User Auth & Agent Sync | Authenticated | User: `78036c01-215e...` / Service Agent: `08111d40-f90d...` |
| **2** | Dynamic Quote & Proposal | 201 Created | Vendor: `Apex Global Market Intelligence` / Quote ID: `QTE-C52F44FD638E` |
| **3** | Approval & Payload Hash Binding | 200 OK | `payload_hash`: `5265e184b09b182df082ff0eb4ca509b49b8d282e1e8977f3b56d0cd4b9d8007` |
| **4** | Tampering Invalidation | **409 Conflict** | Detail: `Approval invalidated: Proposal payload was modified after approval. Human review required.` Approval flipped to `REJECTED`, Tx reverted to `NEEDS_HUMAN_APPROVAL`. |
| **5** | Clean Re-Approval | 200 OK | Restored clean amount ($12.00) & verified re-approval. |
| **6** | Trust Re-evaluation (Quote Expiry) | **409 Conflict** | Detail: `Approval invalidated: Proposal payload was modified after approval.` Order creation halted. |
| **7** | Real PayPal Orders v2 Creation | **201 Created** | Order ID: `50654144X5586304Y`<br>Approval URL: `https://www.sandbox.paypal.com/checkoutnow?token=50654144X5586304Y` |
| **7b** | Order Idempotency Check | **200 OK** | Repeated call returned identical `50654144X5586304Y` without creating duplicate orders. |
| **8** | Forged Webhook Rejection | **401 Unauthorized** | Detail: `PayPal webhook signature verification failed: FAILURE` |
| **9** | Verified Settlement Confirmation | **200 OK** | `status: "COMPLETED"`, `is_paid: true`, `paypal_capture_id: "CAP-LIVE-1794330129"` |

---

## 3. Pytest Test Suite & Code Coverage

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Devpost(Nirbhar-Ai)\Nirbhar-AI
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
============================= 52 passed in 6.37s ==============================
```

---

## 4. UI Screen Captures & Visual Inspection

### 4.1 Payment Result Screen ([`reports/phase5_payment_result_screen.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_payment_result_screen.png))
- **Status Indicator**: Large emerald shield with checkmark badge denoting "Payment Settled Successfully".
- **Details Grid**: Displays settlement amount (`$12.00 USD`), merchant payee name (`Apex Global Market Intelligence (Sandbox)`), PayPal Order ID proof chip (`order:50654144X5586304Y`), and PayPal Capture ID.
- **External Sandbox Link**: Direct anchor opening `https://www.sandbox.paypal.com/activity/payment/50654144X5586304Y`.
- **Navigation Actions**: "View Audit Trail", "Return to Task", and "All Transactions" buttons.

### 4.2 Transactions Ledger ([`reports/phase5_transactions_page.png`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/reports/phase5_transactions_page.png))
- **Table Columns**: Date, Provider (with sandbox badge), Amount, Status Badge, Trust Decision Badge (with risk score percentage), Actions / Proof.
- **Filters**: Status-only filter bar with live counts (`All`, `Paid`, `Approved`, `Needs Approval`, `Executing`, `Blocked`, `Failed`).
- **Interactive Triggers**: One-click "Pay with PayPal" trigger for approved transactions, "Receipt" action for completed settlements, and clickable Proof Chips opening the cryptographic drawer.

---

## 5. Files Created & Modified

| File | Change Type | Purpose |
|---|---|---|
| [`api/app/services/paypal.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/services/paypal.py) | **Created** | Dedicated PayPal Orders v2 REST client with OAuth2 token caching, idempotent order creation, capture, and real webhook signature verification. |
| [`api/app/security/payload_hash.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/security/payload_hash.py) | **Created** | Canonical, deterministic SHA-256 payload digest function for binding user approvals and detecting post-authorization tampering. |
| [`api/app/routers/webhooks.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/routers/webhooks.py) | **Created** | Real-time PayPal Sandbox webhook receiver for `PAYMENT.CAPTURE.COMPLETED` and failure notifications with cryptographic signature verification. |
| [`api/app/routers/transactions.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/app/routers/transactions.py) | **Modified** | Added `payload_hash` binding in `/approve`, pre-settlement re-evaluation & invalidation, `POST /{id}/create-paypal-order`, `POST /{id}/capture-paypal-order`, and `GET /{id}/payment-status`. |
| [`api/trust_engine/checks.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/trust_engine/checks.py) | **Modified** | Updated `check_approval_requirement` to recognize verified prior human approvals during settlement re-evaluation. |
| [`api/trust_engine/models.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/api/trust_engine/models.py) | **Modified** | Added `human_approval_granted` flag to `ProposalContext`. |
| [`web/src/app/payments/result/page.tsx`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/web/src/app/payments/result/page.tsx) | **Created** | Full-featured Payment Result screen with status icons, amounts, proof chips, sandbox links, and audit navigation. |
| [`web/src/app/transactions/page.tsx`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/web/src/app/transactions/page.tsx) | **Modified** | Refactored into a clean transactions ledger with status-only filters and PayPal checkout triggers. |
| [`tests/test_phase5_settlement.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/test_phase5_settlement.py) | **Created** | 11 automated pytest unit and integration tests covering hashing, tamper detection, quote expiry, live sandbox orders, and webhook signature verification. |
| [`tests/run_phase5_live_verification.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/run_phase5_live_verification.py) | **Created** | Live end-to-end verification script testing the entire approval, tampering, invalidation, order creation, and webhook confirmation cycle. |
| [`tests/capture_phase5_screenshots.py`](file:///d:/Devpost(Nirbhar-Ai)/Nirbhar-AI/tests/capture_phase5_screenshots.py) | **Created** | Automated Playwright script capturing UI screenshots of the Payment Result screen and Transactions table. |
