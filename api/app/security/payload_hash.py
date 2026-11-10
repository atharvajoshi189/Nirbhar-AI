import hashlib
import json
from typing import Dict, Any
from decimal import Decimal

def compute_transaction_payload_hash(tx: Dict[str, Any], quote: Dict[str, Any]) -> str:
    """
    Computes a canonical, deterministic SHA-256 payload hash strictly bound to:
    - transaction_id
    - task_id
    - quote_id
    - vendor_name
    - amount
    - currency
    - quote_expires_at
    - quote_amount

    Rule 4 (Zero Client Trust & Anti-Tamper):
    Any tampering with amounts, quotes, or associations changes this digest,
    invalidating previously granted user authorizations.
    """
    quote_details = quote.get("quote_details") or {}
    
    amount_val = tx.get("amount", 0.0)
    quote_amt_val = quote_details.get("amount", quote.get("amount", amount_val))

    canonical_data = {
        "transaction_id": str(tx.get("id", "")),
        "task_id": str(tx.get("task_id", "")),
        "quote_id": str(quote.get("id") or tx.get("quote_id") or ""),
        "vendor_name": str(quote.get("vendor_name") or ""),
        "amount": f"{float(amount_val):.2f}",
        "currency": str(tx.get("currency", "USD")).upper(),
        "quote_expires_at": str(quote_details.get("expires_at") or ""),
        "quote_amount": f"{float(quote_amt_val):.2f}"
    }

    canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
