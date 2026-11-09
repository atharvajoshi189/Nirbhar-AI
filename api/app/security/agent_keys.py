import os
import json
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Supported Agent Roles
AGENT_ROLES = ["coordinator", "research", "service"]
KEYS_STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".agent_keys.json")

class AgentKeyManager:
    """
    Manages Ed25519 cryptographic keypairs for the three system agents:
    - coordinator
    - research
    - service

    Public keys are stored in the Supabase 'agents' table.
    Private keys are retained server-side in secure environment variables or secure local key store.
    """

    def __init__(self, storage_path: str = KEYS_STORAGE_PATH):
        self.storage_path = os.path.abspath(storage_path)
        self._keys: Dict[str, Dict[str, str]] = {}
        self.load_or_generate_all()

    def generate_keypair(self) -> Tuple[str, str]:
        """Generates a raw Ed25519 private/public keypair hex-encoded."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return private_bytes.hex(), public_bytes.hex()

    def load_or_generate_all(self) -> Dict[str, Dict[str, str]]:
        """Loads keys from env or file, generating any missing agent keypairs."""
        keys = {}

        # First attempt to read existing storage file
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    keys = json.load(f)
            except Exception:
                keys = {}

        updated = False
        for role in AGENT_ROLES:
            env_priv = os.getenv(f"AGENT_{role.upper()}_PRIVATE_KEY")
            env_pub = os.getenv(f"AGENT_{role.upper()}_PUBLIC_KEY")

            if env_priv and env_pub:
                keys[role] = {"private_key": env_priv, "public_key": env_pub}
            elif role not in keys or not keys[role].get("private_key"):
                priv, pub = self.generate_keypair()
                keys[role] = {"private_key": priv, "public_key": pub}
                updated = True

        if updated:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(keys, f, indent=2)

        self._keys = keys
        return self._keys

    def get_public_keys(self) -> Dict[str, str]:
        """Returns public keys for all agents (safe to publish to database)."""
        return {role: self._keys[role]["public_key"] for role in AGENT_ROLES if role in self._keys}

    def sign_proposal(self, role: str, payload: Dict[str, Any]) -> str:
        """Signs an agent proposal payload using the agent's private Ed25519 key."""
        if role not in self._keys:
            raise ValueError(f"Unknown or uninitialized agent role: {role}")

        private_hex = self._keys[role]["private_key"]
        private_bytes = bytes.fromhex(private_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)

        canonical_data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = private_key.sign(canonical_data)
        return signature.hex()

    @staticmethod
    def verify_signature(public_key_hex: str, payload: Dict[str, Any], signature_hex: str) -> bool:
        """Verifies an Ed25519 signature over a canonical payload."""
        try:
            public_bytes = bytes.fromhex(public_key_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)
            sig_bytes = bytes.fromhex(signature_hex)
            canonical_data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            public_key.verify(sig_bytes, canonical_data)
            return True
        except Exception:
            return False

agent_key_manager = AgentKeyManager()
