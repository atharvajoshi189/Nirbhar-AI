import json
import base64
from typing import Dict, Any, Tuple, Union
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

def generate_keypair() -> Tuple[str, str]:
    """
    Generates a new Ed25519 keypair for autonomous agent identity.
    Returns (private_key_hex, public_key_hex).
    """
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    
    priv_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return priv_bytes.hex(), pub_bytes.hex()

def _load_private_key(key: Union[str, bytes, Ed25519PrivateKey]) -> Ed25519PrivateKey:
    if isinstance(key, Ed25519PrivateKey):
        return key
    if isinstance(key, str):
        # Hex string or PEM
        if "-----BEGIN" in key:
            return serialization.load_pem_private_key(key.encode(), password=None)
        key_bytes = bytes.fromhex(key)
        return Ed25519PrivateKey.from_private_bytes(key_bytes)
    if isinstance(key, bytes):
        return Ed25519PrivateKey.from_private_bytes(key)
    raise ValueError(f"Unsupported private key format: {type(key)}")

def canonicalize(data: Dict[str, Any]) -> bytes:
    """Serializes a dictionary into canonical deterministic JSON format."""
    # Omit signature fields to prevent circular references
    filtered = {
        k: v for k, v in data.items() 
        if k not in ("signature", "signer_pubkey", "signed_at")
    }
    return json.dumps(filtered, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

def sign_payload(
    payload: Dict[str, Any],
    private_key: Union[str, bytes, Ed25519PrivateKey]
) -> Tuple[str, str, str]:
    """
    Cryptographically signs the canonical proposal payload using Ed25519.
    Returns (signature_hex, public_key_hex, signed_at_iso).
    """
    priv = _load_private_key(private_key)
    pub = priv.public_key()
    
    canonical_bytes = canonicalize(payload)
    sig_bytes = priv.sign(canonical_bytes)
    
    pub_hex = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    signed_at = datetime.now(timezone.utc).isoformat()
    return sig_bytes.hex(), pub_hex, signed_at

def verify_signature(
    payload: Dict[str, Any],
    signature: str,
    public_key: str
) -> bool:
    """Verifies an Ed25519 signature over the canonical proposal payload."""
    try:
        pub_bytes = bytes.fromhex(public_key)
        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        sig_bytes = bytes.fromhex(signature)
        canonical_bytes = canonicalize(payload)
        pub.verify(sig_bytes, canonical_bytes)
        return True
    except Exception:
        return False

