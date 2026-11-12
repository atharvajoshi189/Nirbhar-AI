"""
AgentTrust Python SDK
Authoritative client for autonomous agent spend verification & cryptographic signing.
"""

from typing import Dict, Any, Optional
from .client import AgentTrustClient
from .models import VerificationResult
from .crypto import generate_keypair, sign_payload, verify_signature

__version__ = "0.1.0"

# Module-level convenience functions per Phase 8 Requirement 1

def sign(proposal: Dict[str, Any], key: str) -> Dict[str, Any]:
    """
    Cryptographically signs an agent spend proposal with an Ed25519 private key.
    
    Args:
        proposal: Dictionary containing spend parameters (amount, provider, justification, etc.)
        key: Ed25519 private key in hex or PEM format.

    Returns:
        Updated proposal dictionary with 'signature', 'signer_pubkey', and 'signed_at'.
    """
    client = AgentTrustClient(private_key=key)
    return client.sign(proposal)

def verify(
    proposal: Dict[str, Any],
    api_base: str = "http://127.0.0.1:8000",
    api_key: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> VerificationResult:
    """
    Evaluates an agent proposal through the live Nirbhar AI Trust Engine API.

    Args:
        proposal: Signed or unsigned proposal dictionary.
        api_base: Base URL of the Nirbhar AI core API.
        api_key: Optional API key for authenticated requests.
        idempotency_key: Optional UUID header for idempotent execution.

    Returns:
        VerificationResult with decision (APPROVED, NEEDS_HUMAN_APPROVAL, BLOCKED),
        reason codes, risk score, and verifiable proof chip.
    """
    client = AgentTrustClient(api_base=api_base, api_key=api_key)
    return client.verify(proposal, idempotency_key=idempotency_key)

__all__ = [
    "AgentTrustClient",
    "VerificationResult",
    "generate_keypair",
    "sign_payload",
    "verify_signature",
    "sign",
    "verify",
]

