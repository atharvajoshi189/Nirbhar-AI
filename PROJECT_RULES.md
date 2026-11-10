# Nirbhar AI — Project Rules & Architecture Standards

These rules are strict, foundational, and non-negotiable across every phase of development.

---

### Rule 1: NO-SIMULATION RULE
- **Never use mock data, fake responses, hardcoded results, placeholder providers, `Math.random()` outputs, or `setTimeout` fake loading.**
- Every agent output must originate from a real **Gemini API** call.
- Every provider/research result must originate from a real web search call (e.g. Tavily).
- Every payment must go through the real **PayPal Sandbox REST API**.
- Every persistent record must be stored in the real **Supabase** database.
- **Fail Fast & Explicitly**: If a credential, secret, or environment variable is missing, halt execution and inform the user immediately. Do not fall back to fake or mock data under any circumstances.

---

### Rule 2: PROOF RULE
- Every agent step, quote, trust decision, payment, and audit event must store verifiable metadata:
  - `request_id`
  - `model_name`
  - `latency_ms`
  - `source_urls`
  - `paypal_order_id` / `paypal_capture_id`
  - Cryptographic hashes (`payload_hash`, `signature`, etc.)
- In the frontend UI, every entity or action must display a small **Proof Chip** that users can click to open a sliding drawer/sheet revealing the exact raw payload, headers, cryptographic hash, and upstream response metadata.

---

### Rule 3: STACK SPECIFICATION
- **/web**: Next.js (App Router, TypeScript) + Tailwind CSS + shadcn/ui.
- **/api**: FastAPI (Python 3.11, async) core API orchestrator & Trust Engine.
- **/vendor-gateway**: Separate FastAPI service acting as the sandboxed checkout / vendor bridge.
- **/sdk**: Client SDK (Python/TypeScript) for agent interactions with the trust layer.
- **Persistence & Realtime**: Supabase Postgres + Supabase Auth + Realtime subscriptions.
- **Job Queue**: Redis + ARQ for asynchronous background agent jobs.
- **LLM / Agent Engine**: Google Gemini API via official SDKs.
- **External Search**: Tavily Search API.
- **Payments**: PayPal Orders v2 REST API + PayPal Sandbox Webhooks.

---

### Rule 4: SECURITY & AUTHORIZATION
- PayPal credentials, client secrets, and transaction capture logic must live **exclusively on the backend** (`/api` / `/vendor-gateway`).
- **Zero Client Trust**: Never trust amounts, vendor names, provider identities, agent IDs, or approval flags sent from the frontend. All state and authoritative business logic must be resolved server-side.
- **Agent Sandbox Barrier**: Agents can NEVER directly call PayPal or trigger payments. Agents can only generate structured payment proposals for the Trust Engine.
- **Fail Closed**: Any error, missing parameter, schema mismatch, network glitch, or unverified webhook signature results in an immediate `BLOCKED` decision or uncommitted payment.
- **Secret Hygiene**: All credentials must be stored in `.env` (gitignored). Only `.env.example` is committed to git.

---

### Rule 5: UI & DESIGN SYSTEM
- **Palette & Typography**: Clean, professional, minimal text. White / slate neutral palette with a single primary `indigo` accent (`indigo-600`). Inter font typography, strict 8px spatial grid.
- **Left Sidebar Navigation**: Exactly 5 navigation items:
  1. `Dashboard`
  2. `New Task`
  3. `Transactions`
  4. `Audit Log`
  5. `Red Team`
- **Status Badges**:
  - `APPROVED`: Emerald / Green
  - `NEEDS_HUMAN_APPROVAL`: Amber / Yellow
  - `BLOCKED`: Rose / Red
  - `PENDING`: Slate / Grey
- **State Handling**: Every screen must have explicit, polished empty states, skeleton loaders, and actionable error states.
- **Footer Health Strip**: Persistent live status strip at the bottom of the viewport showing real-time connectivity and health for:
  - Gemini API
  - Supabase Database & Auth
  - PayPal Sandbox API

---

### Rule 6: PHASE WORKFLOW
- After every phase is executed, create `/reports/phase-N.md` detailing:
  1. What was built.
  2. Files created or changed.
  3. Automated tests and manual validation commands executed.
  4. Real results with verifiable evidence (system logs, live API response payloads, IDs, timestamps).
  5. Known issues, constraints, or next steps.
- **Never claim something works without running it and inspecting actual output.**

