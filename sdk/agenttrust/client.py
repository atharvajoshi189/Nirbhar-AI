import os
import httpx
from typing import Dict, Any, Optional, Union
from .crypto import sign_payload, generate_keypair
from .models import VerificationResult

class AgentTrustClient:
    """Client SDK for autonomous agents interacting with Nirbhar AI Trust Engine."""

    def __init__(
        self,
        api_base: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or os.getenv("AGENTTRUST_API_KEY")
        self.private_key = private_key or os.getenv("AGENT_PRIVATE_KEY")
        self.timeout = timeout

    def sign(
        self,
        proposal: Dict[str, Any],
        private_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Signs the proposal dictionary with the agent's Ed25519 private key.
        Attaches 'signature', 'signer_pubkey', and 'signed_at' fields.
        """
        key_to_use = private_key or self.private_key
        if not key_to_use:
            raise ValueError("No private key provided for proposal signing.")
        
        sig_hex, pub_hex, signed_at = sign_payload(proposal, key_to_use)
        signed_proposal = dict(proposal)
        signed_proposal["signature"] = sig_hex
        signed_proposal["signer_pubkey"] = pub_hex
        signed_proposal["signed_at"] = signed_at
        return signed_proposal

    def verify(
        self,
        proposal: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> VerificationResult:
        """
        Submits the proposal to the real Nirbhar AI API for deterministic evaluation.
        Calls POST /trust/verify.
        """
        url = f"{self.api_base}/trust/verify"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=proposal, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Trust evaluation request failed with HTTP {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            return VerificationResult(**data)

    def get_health(self) -> Dict[str, Any]:
        """Queries the live health endpoint of the Nirbhar AI core API."""
        url = f"{self.api_base}/health"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

