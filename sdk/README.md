# AgentTrust Python SDK

The official Python client for autonomous AI agents integrating with **Nirbhar AI** — the zero-trust payment verification and spend enforcement gateway.

---

## Installation

```bash
pip install ./sdk
# or from source:
pip install -e ./sdk
```

---

## Quickstart

### 1. Module-level Usage (`agenttrust.sign` & `agenttrust.verify`)

```python
import agenttrust

# Step 1: Generate an agent Ed25519 keypair
priv_key, pub_key = agenttrust.generate_keypair()

# Step 2: Define procurement proposal
proposal = {
    "amount": 12.00,
    "currency": "USD",
    "provider_name": "CloudScale Infrastructure",
    "provider_url": "https://cloudscale.io/api",
    "proposal_category": "cloud_compute",
    "justification": "Provisioning 2x compute workers for data indexing."
}

# Step 3: Sign proposal with agent key
signed_proposal = agenttrust.sign(proposal, key=priv_key)

# Step 4: Verify against live Nirbhar AI Trust Engine
result = agenttrust.verify(signed_proposal, api_base="http://127.0.0.1:8000")

print(f"Decision: {result.decision}")       # APPROVED, NEEDS_HUMAN_APPROVAL, or BLOCKED
print(f"Risk Score: {result.risk_score}")   # 0.0 to 1.0
print(f"Proof Hash: {result.proof_chip['sha256']}")
```

---

### 2. Object-Oriented Client (`AgentTrustClient`)

```python
from agenttrust import AgentTrustClient

client = AgentTrustClient(
    api_base="http://127.0.0.1:8000",
    private_key="<agent-ed25519-private-key-hex>"
)

# Sign and verify in one flow
signed = client.sign(proposal)
result = client.verify(signed)

if result.is_approved:
    print("Proposal approved deterministically! Proceeding to checkout.")
elif result.needs_human_approval:
    print("User approval required before payment.")
else:
    print(f"Proposal blocked: {result.explanation} Reasons: {result.reason_codes}")
```

---

## Invariant Guarantees

1. **Non-repudiation**: Every proposal is canonically formatted and signed with Ed25519.
2. **Zero Simulation**: All evaluations query the active Nirbhar AI Trust Engine API.
3. **Fail-Closed**: Any policy violation, signature mismatch, or budget exceedance yields `BLOCKED`.

