import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel

GENESIS_PREV_HASH = "0" * 64

class AuditEventCreate(BaseModel):
    user_id: str
    task_id: Optional[str] = None
    transaction_id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]

class AuditEventRecord(BaseModel):
    id: Optional[str] = None
    user_id: str
    task_id: Optional[str] = None
    transaction_id: Optional[str] = None
    event_type: str
    sequence_number: int
    prev_hash: str
    hash: str
    payload: Dict[str, Any]
    created_at: str

class ChainVerificationResult(BaseModel):
    valid: bool
    total_events: int
    latest_hash: Optional[str] = None
    tampered_at_sequence: Optional[int] = None
    error_details: Optional[str] = None
    verified_at: str

class AuditChainService:
    def __init__(self, audit_secret: Optional[str] = None):
        self.audit_secret = audit_secret or os.getenv("AUDIT_SECRET", "nirbhar_tamper_evident_audit_secret_2026")
        self._in_memory_events: List[Dict[str, Any]] = []

    def canonicalize_payload(self, payload: Dict[str, Any]) -> str:
        """Serializes payload into canonical JSON string (deterministic whitespace & key sorting)."""
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def compute_event_hash(self, prev_hash: str, payload: Dict[str, Any]) -> str:
        """
        Computes SHA-256 over: prev_hash + canonical_payload + AUDIT_SECRET.
        Guarantees that any change in payload, order, or previous hash breaks verification.
        """
        canonical_str = self.canonicalize_payload(payload)
        preimage = f"{prev_hash}:{canonical_str}:{self.audit_secret}".encode("utf-8")
        return hashlib.sha256(preimage).hexdigest()

    def build_event(
        self,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        sequence_number: int,
        prev_hash: Optional[str] = None,
        task_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> AuditEventRecord:
        """Constructs a cryptographically linked audit event."""
        prior_hash = prev_hash if (prev_hash and prev_hash != "") else GENESIS_PREV_HASH
        event_hash = self.compute_event_hash(prior_hash, payload)
        now_iso = datetime.now(timezone.utc).isoformat()

        return AuditEventRecord(
            user_id=user_id,
            task_id=task_id,
            transaction_id=transaction_id,
            event_type=event_type,
            sequence_number=sequence_number,
            prev_hash=prior_hash,
            hash=event_hash,
            payload=payload,
            created_at=now_iso,
        )

    def append_event(
        self,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Authoritatively queries the current user's audit chain sequence,
        computes the next linked SHA-256 hash, and inserts the immutable record into Supabase.
        Falls back to in-memory cryptographic chain if database credentials are not configured (e.g. CI testing).
        """
        supabase = None
        try:
            from app.db.supabase import get_supabase_admin_client
            supabase = get_supabase_admin_client()
        except Exception:
            supabase = None

        if supabase is None:
            user_events = [e for e in self._in_memory_events if e.get("user_id") == user_id]
            if user_events:
                last_event = user_events[-1]
                next_seq = last_event["sequence_number"] + 1
                prev_hash = last_event["hash"]
            else:
                next_seq = 1
                prev_hash = GENESIS_PREV_HASH

            event = self.build_event(
                user_id=user_id,
                event_type=event_type,
                payload=payload,
                sequence_number=next_seq,
                prev_hash=prev_hash,
                task_id=task_id,
                transaction_id=transaction_id,
            )
            data = event.model_dump(exclude_none=True)
            data["id"] = f"audit_mem_{uuid.uuid4().hex[:12]}"
            self._in_memory_events.append(data)
            return data

        # Find latest sequence number for this user in Supabase
        res = (
            supabase.table("audit_events")
            .select("sequence_number, hash")
            .eq("user_id", user_id)
            .order("sequence_number", desc=True)
            .limit(1)
            .execute()
        )

        if res.data and len(res.data) > 0:
            last_seq = res.data[0]["sequence_number"]
            prev_hash = res.data[0]["hash"]
            next_seq = last_seq + 1
        else:
            next_seq = 1
            prev_hash = GENESIS_PREV_HASH

        event = self.build_event(
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            sequence_number=next_seq,
            prev_hash=prev_hash,
            task_id=task_id,
            transaction_id=transaction_id,
        )

        insert_data = event.model_dump(exclude_none=True)
        insert_res = supabase.table("audit_events").insert(insert_data).execute()
        if not insert_res.data:
            raise RuntimeError("Failed to persist audit event in Supabase")
        return insert_res.data[0]

    def get_in_memory_events(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        events = self._in_memory_events
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        return list(reversed(events))[:limit]

    def verify_chain(self, events: List[Dict[str, Any]]) -> ChainVerificationResult:
        """
        Recomputes the entire audit chain from genesis to tip.
        Detects tampering, out-of-order sequence numbers, or payload alterations.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        if not events:
            return ChainVerificationResult(
                valid=True,
                total_events=0,
                latest_hash=None,
                verified_at=now_iso,
            )

        # Sort by sequence_number
        sorted_events = sorted(events, key=lambda x: x.get("sequence_number", 0))

        expected_prev_hash = GENESIS_PREV_HASH

        for idx, event in enumerate(sorted_events):
            seq = event.get("sequence_number", 0)
            prev_h = event.get("prev_hash")
            stored_h = event.get("hash")
            payload = event.get("payload", {})

            # 1. Verify sequence continuity
            if seq != idx + 1:
                return ChainVerificationResult(
                    valid=False,
                    total_events=len(sorted_events),
                    tampered_at_sequence=seq,
                    error_details=f"Sequence discontinuity: expected sequence {idx + 1}, found {seq}",
                    verified_at=now_iso,
                )

            # 2. Verify backward link
            if prev_h != expected_prev_hash:
                return ChainVerificationResult(
                    valid=False,
                    total_events=len(sorted_events),
                    tampered_at_sequence=seq,
                    error_details=f"Hash linkage broken at sequence {seq}. Expected prev_hash {expected_prev_hash}, found {prev_h}",
                    verified_at=now_iso,
                )

            # 3. Recompute SHA-256 hash over payload and AUDIT_SECRET
            recomputed_hash = self.compute_event_hash(prev_h, payload)
            if recomputed_hash != stored_h:
                return ChainVerificationResult(
                    valid=False,
                    total_events=len(sorted_events),
                    tampered_at_sequence=seq,
                    error_details=f"Tamper detected at sequence {seq}! Stored hash {stored_h} does not match computed hash {recomputed_hash}",
                    verified_at=now_iso,
                )

            expected_prev_hash = stored_h

        return ChainVerificationResult(
            valid=True,
            total_events=len(sorted_events),
            latest_hash=expected_prev_hash,
            verified_at=now_iso,
        )

audit_service = AuditChainService()

