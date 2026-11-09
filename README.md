# AgentTrust AI

> Independent trust and authorization layer sitting between autonomous AI agents and payment rails (PayPal Sandbox).

## Architecture Overview

AgentTrust AI ensures autonomous AI agents cannot execute arbitrary, malicious, or out-of-budget transactions. 
1. **User creates a task** with an explicit budget and constraints.
2. **AI Agents plan and research** vendors, proposing itemized payment actions.
3. **Deterministic Trust Engine** evaluates transactions: `APPROVED`, `NEEDS_HUMAN_APPROVAL`, or `BLOCKED`.
4. **PayPal Sandbox REST API** is only contacted for user-authorized or engine-approved payments.
5. **Verifiable Audit Trail**: Every step, prompt, quote, and webhook retains cryptographic proof chips viewable directly in the UI.

## Monorepo Layout

- `PROJECT_RULES.md` — Mandatory architectural rules (No mock data, proof chips, fail-closed security).
- `/web` — Next.js 14+ (App Router, TypeScript, Tailwind CSS, shadcn/ui design system).
- `/api` — FastAPI (Python 3.11, async) core orchestrator, Trust Engine, and health telemetry.
- `/vendor-gateway` — Dedicated sandboxed payment execution service interfacing with PayPal Sandbox.
- `/sdk` — Client library for agents to propose transactions to AgentTrust AI.
- `/tests` — End-to-end and integration test suites.
- `/reports` — Detailed phase completion reports with verifiable logs and evidence.

## Quick Start

### 1. Environment Setup
Copy the environment template:
```bash
cp .env.example .env
```
Fill in real keys for:
- `GEMINI_API_KEY`
- `SUPABASE_URL` & `SUPABASE_ANON_KEY`
- `PAYPAL_CLIENT_ID` & `PAYPAL_CLIENT_SECRET`

### 2. Running Services

#### Backend API (/api)
```bash
cd api
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Vendor Gateway (/vendor-gateway)
```bash
cd vendor-gateway
python -m venv .venv
# activate venv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

#### Frontend Web UI (/web)
```bash
cd web
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to view the application shell and live service health indicators.

