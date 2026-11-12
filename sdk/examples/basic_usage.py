#!/usr/bin/env python3
"""
Example demonstrating how an AI agent uses the AgentTrust SDK
to sign an operational payment proposal and verify it with the Nirbhar AI Trust Engine.
"""

import os
import sys

# Add sdk to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import agenttrust

def main():
    print("=" * 60)
    print("AgentTrust Python SDK: Autonomous Spend Verification Flow")
    print("=" * 60)

    # 1. Generate autonomous agent identity keypair
    print("\n1. Generating agent Ed25519 identity keypair...")
    private_key, public_key = agenttrust.generate_keypair()
    print(f"   Private Key: {private_key[:16]}...{private_key[-8:]}")
    print(f"   Public Key:  {public_key[:16]}...{public_key[-8:]}")

    # 2. Construct operational spend proposal
    proposal = {
        "amount": 12.00,
        "currency": "USD",
        "provider_name": "CloudScale Infrastructure Solutions",
        "provider_url": "https://cloudscale.io/api",
        "proposal_category": "cloud_compute",
        "justification": "Procuring 2x ephemeral compute instances for NLP indexing benchmark.",
        "signer_pubkey": public_key
    }
    print(f"\n2. Proposed spend: ${proposal['amount']} {proposal['currency']} -> {proposal['provider_name']}")

    # 3. Cryptographically sign the proposal
    print("\n3. Signing proposal canonically with Ed25519 key...")
    signed_proposal = agenttrust.sign(proposal, key=private_key)
    print(f"   Signature: {signed_proposal['signature'][:24]}...")
    print(f"   Signed At: {signed_proposal['signed_at']}")

    # 4. Verify proposal against live API
    api_base = os.getenv("NIRBHAR_API_URL", "http://127.0.0.1:8000")
    print(f"\n4. Submitting signed proposal to Nirbhar AI API ({api_base}/trust/verify)...")
    try:
        result = agenttrust.verify(signed_proposal, api_base=api_base)
        print(f"\n--- EVALUATION OUTCOME ---")
        print(f"   Decision:     {result.decision}")
        print(f"   Risk Score:   {result.risk_score}")
        print(f"   Reason Codes: {result.reason_codes}")
        print(f"   Explanation:  {result.explanation}")
        print(f"   SHA-256 Proof: {result.proof_chip.get('sha256', 'N/A')}")
        print(f"   Latency:      {result.proof_chip.get('latency_ms', 0)}ms")
        print("=" * 60)
    except Exception as e:
        print(f"\n[NOTE] Verification query completed with notice: {e}")
        print("Ensure Core API is running at http://127.0.0.1:8000 for live endpoint response.")

if __name__ == "__main__":
    main()

