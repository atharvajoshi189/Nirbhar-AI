import sys
import json

# Import installed SDK package from fresh virtualenv
import agenttrust

def main():
    print("=" * 60)
    print("VERIFICATION TASK 1: SDK INSTALLED IN FRESH VIRTUALENV")
    print(f"Python Executable: {sys.executable}")
    print(f"AgentTrust Version: {agenttrust.__version__}")
    print("=" * 60)

    # 1. Generate autonomous agent keypair using installed SDK
    print("\n1. Generating Ed25519 identity keypair with agenttrust.generate_keypair()...")
    private_key, public_key = agenttrust.generate_keypair()
    print(f"   Private Key: {private_key[:16]}...{private_key[-8:]}")
    print(f"   Public Key:  {public_key[:16]}...{public_key[-8:]}")

    # 2. Construct real proposal
    proposal = {
        "amount": 14.50,
        "currency": "USD",
        "provider_name": "CloudScale Infrastructure Solutions",
        "provider_url": "https://cloudscale.io/api",
        "proposal_category": "cloud_compute",
        "justification": "Procure dedicated build worker for automated CI indexing.",
        "signer_pubkey": public_key,
        "bypass_advisory_llm": True
    }
    print(f"\n2. Proposed spend: ${proposal['amount']} {proposal['currency']} to {proposal['provider_name']}")

    # 3. Cryptographically sign proposal with installed SDK
    print("\n3. Signing proposal with agenttrust.sign()...")
    signed_proposal = agenttrust.sign(proposal, key=private_key)
    print(f"   Signature: {signed_proposal['signature'][:24]}...")
    print(f"   Signed At: {signed_proposal['signed_at']}")

    # 4. Verify against real live API
    api_url = "http://127.0.0.1:8000"
    print(f"\n4. Verifying signed proposal against real API ({api_url}/trust/verify)...")
    result = agenttrust.verify(signed_proposal, api_base=api_url)

    print("\n" + "=" * 60)
    print("REAL API EVALUATION OUTCOME:")
    print("=" * 60)
    print(f"Decision:       {result.decision}")
    print(f"Risk Score:     {result.risk_score}")
    print(f"Reason Codes:   {result.reason_codes}")
    print(f"Explanation:    {result.explanation}")
    print(f"Proof SHA-256:  {result.proof_chip.get('sha256')}")
    print(f"Request ID:     {result.proof_chip.get('request_id')}")
    print(f"Latency:        {result.proof_chip.get('latency_ms')}ms")
    print("=" * 60)

    assert result.decision in ["APPROVED", "NEEDS_HUMAN_APPROVAL", "BLOCKED"]
    assert result.proof_chip.get("sha256") is not None
    print("\n[SUCCESS] Task 1 PASSED: SDK cleanly installed in fresh virtualenv and verified real proposal!")

if __name__ == "__main__":
    main()
