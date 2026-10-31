from __future__ import annotations

"""Vendor-neutral device evidence authenticity.

This module proves possession of a registered device key, not hardware-backed
attestation. Hardware roots of trust require a separately reviewed provider.
"""

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import math
import secrets
import sqlite3
from typing import Protocol
from uuid import UUID


_DEVICE_ATTESTATION_DOMAIN = "PHyAI-DEVICE-EVIDENCE-V1"


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


@dataclass(frozen=True, slots=True)
class DeviceEvidenceChallenge:
    device_id: str
    attempt_id: UUID
    sequence: int
    nonce: str
    issued_at_ns: int
    expires_at_ns: int

    def __post_init__(self) -> None:
        _required_text("device_id", self.device_id)
        if not isinstance(self.attempt_id, UUID):
            raise ValueError("attempt_id must be a UUID")
        _nonnegative_int("sequence", self.sequence)
        _required_text("nonce", self.nonce)
        if len(self.nonce) < 32:
            raise ValueError("nonce must contain at least 32 characters")
        _nonnegative_int("issued_at_ns", self.issued_at_ns)
        _nonnegative_int("expires_at_ns", self.expires_at_ns)
        if self.expires_at_ns <= self.issued_at_ns:
            raise ValueError("challenge expiry must follow issue time")


@dataclass(frozen=True, slots=True)
class DeviceEvidenceAttestation:
    device_id: str
    attempt_id: UUID
    sequence: int
    timestamp_ns: int
    result_digest: str
    nonce: str
    key_id: str
    algorithm: str
    signature: str

    def __post_init__(self) -> None:
        _required_text("device_id", self.device_id)
        if not isinstance(self.attempt_id, UUID):
            raise ValueError("attempt_id must be a UUID")
        _nonnegative_int("sequence", self.sequence)
        _nonnegative_int("timestamp_ns", self.timestamp_ns)
        _required_text("result_digest", self.result_digest)
        _required_text("nonce", self.nonce)
        _required_text("key_id", self.key_id)
        _required_text("algorithm", self.algorithm)
        _required_text("signature", self.signature)


@dataclass(frozen=True, slots=True)
class DeviceKeyRecord:
    device_id: str
    key_id: str
    algorithm: str
    secret: bytes
    enabled: bool = True

    def __post_init__(self) -> None:
        _required_text("device_id", self.device_id)
        _required_text("key_id", self.key_id)
        _required_text("algorithm", self.algorithm)
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("reference HMAC key must contain at least 32 bytes")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be boolean")


class DeviceKeyRegistry(Protocol):
    def resolve(self, device_id: str, key_id: str) -> DeviceKeyRecord | None: ...


class DeviceChallengeStore(Protocol):
    def consume_once(
        self, nonce: str, binding_digest: str, device_id: str, sequence: int
    ) -> bool: ...


class DeviceEvidenceSigner(Protocol):
    key_id: str
    algorithm: str

    def sign(self, payload: bytes) -> str: ...


class HMACDeviceEvidenceSigner:
    """Software reference signer only; this is not a TPM/TEE/secure-element key."""

    algorithm = "HMAC-SHA256"

    def __init__(self, key_id: str, secret: bytes) -> None:
        _required_text("key_id", key_id)
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("device HMAC secret must contain at least 32 bytes")
        self.key_id = key_id
        self._secret = bytes(secret)

    def sign(self, payload: bytes) -> str:
        return hmac.new(self._secret, payload, "sha256").hexdigest()


class InMemoryDeviceKeyRegistry:
    """Test/reference registry. Production key custody must be externalized."""

    def __init__(self, records: tuple[DeviceKeyRecord, ...] = ()) -> None:
        self._records = {(item.device_id, item.key_id): item for item in records}

    def register(self, record: DeviceKeyRecord) -> None:
        key = (record.device_id, record.key_id)
        if key in self._records:
            raise ValueError("device key already registered")
        self._records[key] = record

    def resolve(self, device_id: str, key_id: str) -> DeviceKeyRecord | None:
        return self._records.get((device_id, key_id))


class SQLiteDeviceChallengeStore:
    """Local atomic nonce-consumption store; not a multi-host replay service."""

    def __init__(self, database_path: str, *, timeout_seconds: float = 5.0) -> None:
        if not isinstance(database_path, str) or not database_path.strip() or database_path == ":memory:":
            raise ValueError("database_path must be a persistent filesystem path")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be a positive finite number")
        self._path = database_path
        self._timeout = float(timeout_seconds)
        with sqlite3.connect(self._path, timeout=self._timeout) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS phase_device_consumed_challenges (
                    nonce TEXT PRIMARY KEY,
                    binding_digest TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS phase_device_sequence_counters (
                    device_id TEXT PRIMARY KEY,
                    last_sequence INTEGER NOT NULL CHECK (last_sequence >= 0)
                )
            """)

    def consume_once(
        self, nonce: str, binding_digest: str, device_id: str, sequence: int
    ) -> bool:
        _required_text("nonce", nonce)
        _required_text("binding_digest", binding_digest)
        _required_text("device_id", device_id)
        _nonnegative_int("sequence", sequence)
        connection = sqlite3.connect(self._path, timeout=self._timeout, isolation_level=None)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO phase_device_consumed_challenges (nonce, binding_digest) VALUES (?, ?)",
                    (nonce, binding_digest),
                )
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                return False
            previous = connection.execute(
                "SELECT last_sequence FROM phase_device_sequence_counters WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if previous is not None and sequence <= previous[0]:
                connection.execute("ROLLBACK")
                return False
            connection.execute(
                """
                INSERT INTO phase_device_sequence_counters (device_id, last_sequence)
                VALUES (?, ?)
                ON CONFLICT(device_id) DO UPDATE SET last_sequence = excluded.last_sequence
                """,
                (device_id, sequence),
            )
            connection.execute("COMMIT")
            return True
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()


def issue_device_challenge(
    device_id: str, attempt_id: UUID, sequence: int, *,
    now_ns: int, lifetime_ns: int,
) -> DeviceEvidenceChallenge:
    _required_text("device_id", device_id)
    if not isinstance(attempt_id, UUID):
        raise ValueError("attempt_id must be a UUID")
    _nonnegative_int("sequence", sequence)
    _nonnegative_int("now_ns", now_ns)
    if isinstance(lifetime_ns, bool) or not isinstance(lifetime_ns, int) or lifetime_ns <= 0:
        raise ValueError("lifetime_ns must be a positive integer")
    expires = now_ns + lifetime_ns
    if expires <= now_ns:
        raise ValueError("challenge expiry overflow")
    return DeviceEvidenceChallenge(
        device_id, attempt_id, sequence, secrets.token_urlsafe(32), now_ns, expires
    )


def _canonical_attestation_payload(
    challenge: DeviceEvidenceChallenge,
    timestamp_ns: int,
    result_digest: str,
    key_id: str,
    algorithm: str,
) -> bytes:
    body = {
        "domain": _DEVICE_ATTESTATION_DOMAIN,
        "device_id": challenge.device_id,
        "attempt_id": str(challenge.attempt_id),
        "sequence": challenge.sequence,
        "timestamp_ns": timestamp_ns,
        "result_digest": result_digest,
        "nonce": challenge.nonce,
        "challenge_issued_at_ns": challenge.issued_at_ns,
        "challenge_expires_at_ns": challenge.expires_at_ns,
        "key_id": key_id,
        "algorithm": algorithm,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def create_device_attestation(
    challenge: DeviceEvidenceChallenge,
    *, timestamp_ns: int, result_digest: str, signer: DeviceEvidenceSigner,
) -> DeviceEvidenceAttestation:
    _nonnegative_int("timestamp_ns", timestamp_ns)
    _required_text("result_digest", result_digest)
    payload = _canonical_attestation_payload(
        challenge, timestamp_ns, result_digest, signer.key_id, signer.algorithm
    )
    return DeviceEvidenceAttestation(
        challenge.device_id, challenge.attempt_id, challenge.sequence,
        timestamp_ns, result_digest, challenge.nonce, signer.key_id,
        signer.algorithm, signer.sign(payload),
    )


class DeviceAttestationVerifier:
    """Verifies device key possession and consumes each challenge exactly once."""

    def __init__(self, registry: DeviceKeyRegistry, challenge_store: DeviceChallengeStore) -> None:
        self._registry = registry
        self._challenge_store = challenge_store

    def verify(
        self, challenge: DeviceEvidenceChallenge, attestation: DeviceEvidenceAttestation,
        evidence: object, *, now_ns: int,
    ) -> None:
        from src.production_hardening.phase17_evidence import ExecutionEvidence

        _nonnegative_int("now_ns", now_ns)
        if not isinstance(evidence, ExecutionEvidence):
            raise TypeError("evidence must be an ExecutionEvidence instance")
        if now_ns < challenge.issued_at_ns or now_ns >= challenge.expires_at_ns:
            raise PermissionError("device challenge is not currently valid")
        if (
            attestation.device_id != challenge.device_id
            or attestation.attempt_id != challenge.attempt_id
            or attestation.sequence != challenge.sequence
            or attestation.nonce != challenge.nonce
        ):
            raise ValueError("device attestation does not match challenge")
        if (
            evidence.device_id != challenge.device_id
            or evidence.attempt_id != challenge.attempt_id
            or evidence.sequence != challenge.sequence
            or evidence.timestamp_ns != attestation.timestamp_ns
            or evidence.result_digest != attestation.result_digest
        ):
            raise ValueError("device attestation does not match execution evidence")
        if attestation.timestamp_ns < challenge.issued_at_ns or attestation.timestamp_ns > now_ns:
            raise PermissionError("device evidence timestamp is outside challenge verification window")
        record = self._registry.resolve(attestation.device_id, attestation.key_id)
        if record is None or not record.enabled:
            raise PermissionError("device key is not registered or is disabled")
        if record.device_id != attestation.device_id or record.key_id != attestation.key_id:
            raise PermissionError("device key identity mismatch")
        if record.algorithm != attestation.algorithm or record.algorithm != "HMAC-SHA256":
            raise PermissionError("unsupported device attestation algorithm")
        payload = _canonical_attestation_payload(
            challenge, attestation.timestamp_ns, attestation.result_digest,
            attestation.key_id, attestation.algorithm,
        )
        expected = hmac.new(record.secret, payload, "sha256").hexdigest()
        if not hmac.compare_digest(expected, attestation.signature):
            raise PermissionError("invalid device evidence signature")
        binding = sha256(payload + b"|" + attestation.signature.encode("ascii")).hexdigest()
        if not self._challenge_store.consume_once(
            challenge.nonce, binding, challenge.device_id, challenge.sequence
        ):
            raise PermissionError("device challenge replay detected")
