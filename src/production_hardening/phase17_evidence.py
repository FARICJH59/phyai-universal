from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
from typing import Mapping, Protocol
from uuid import UUID

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedHoareClient


_IDENTITY_FACTORY_TOKEN = object()
_RECEIPT_FACTORY_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class ExecutionIdentity:
    """Immutable identity binding created only from governed admission."""

    tenant_id: str
    project_id: str
    command_id: UUID
    attempt_id: UUID
    artifact_hash: str
    capability_id: str
    lease_id: str
    fence_id: str
    policy_digest: str
    request_digest: str

    def __init__(
        self,
        tenant_id: str,
        project_id: str,
        command_id: UUID,
        attempt_id: UUID,
        artifact_hash: str,
        capability_id: str,
        lease_id: str,
        fence_id: str,
        policy_digest: str,
        request_digest: str = "",
        *,
        _provenance_token: object | None = None,
    ) -> None:
        if _provenance_token is not _IDENTITY_FACTORY_TOKEN:
            raise PermissionError("execution identity must originate from governed admission")
        for name, value in (("tenant_id", tenant_id), ("project_id", project_id), ("artifact_hash", artifact_hash), ("capability_id", capability_id), ("lease_id", lease_id), ("fence_id", fence_id), ("policy_digest", policy_digest), ("request_digest", request_digest)):
            if not value.strip():
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "command_id", command_id)
        object.__setattr__(self, "attempt_id", attempt_id)
        object.__setattr__(self, "artifact_hash", artifact_hash)
        object.__setattr__(self, "capability_id", capability_id)
        object.__setattr__(self, "lease_id", lease_id)
        object.__setattr__(self, "fence_id", fence_id)
        object.__setattr__(self, "policy_digest", policy_digest)
        object.__setattr__(self, "request_digest", request_digest)

    def canonical(self) -> str:
        return "|".join((self.tenant_id, self.project_id, str(self.command_id), str(self.attempt_id), self.artifact_hash, self.capability_id, self.lease_id, self.fence_id, self.policy_digest, self.request_digest))

    def digest(self) -> str:
        return sha256(self.canonical().encode("utf-8")).hexdigest()

    @classmethod
    def from_governed_admission(
        cls,
        command: ControlCommand,
        artifact_hash: str,
        policy_digest: str,
        admission: GovernedAdmission,
        *,
        policy_context: Mapping[str, str],
    ) -> "ExecutionIdentity":
        if not admission.accepted:
            raise PermissionError("cannot create execution identity from denied admission")
        if admission.attempt_id != command.attempt_id:
            raise ValueError("governed admission attempt identity mismatch")
        if not admission.capability_id or not admission.lease_id or not admission.fence_id:
            raise ValueError("accepted admission is missing authority")
        if not admission.request_digest.strip():
            raise ValueError("accepted admission is missing request binding")
        if policy_context.get("policy_digest") != policy_digest:
            raise ValueError("policy digest mismatch")
        expected_request_digest = GovernedHoareClient.digest_request(
            command, artifact_hash, policy_context
        )
        if admission.request_digest != expected_request_digest:
            raise ValueError("governed admission request digest mismatch")
        return cls(
            command.tenant_id, command.project_id, command.command_id,
            admission.attempt_id, artifact_hash, admission.capability_id,
            admission.lease_id, admission.fence_id, policy_digest,
            admission.request_digest, _provenance_token=_IDENTITY_FACTORY_TOKEN
        )


@dataclass(frozen=True, slots=True)
class SignedAdmissionArtifact:
    identity: ExecutionIdentity
    identity_digest: str
    key_id: str
    algorithm: str
    signature: str

    def __post_init__(self) -> None:
        if self.identity_digest != self.identity.digest():
            raise ValueError("admission identity digest mismatch")
        if not self.key_id.strip() or not self.algorithm.strip() or not self.signature.strip():
            raise ValueError("signed admission metadata is required")


class AdmissionSigner(Protocol):
    key_id: str
    algorithm: str

    def sign(self, message: bytes) -> str: ...
    def verify(self, message: bytes, signature: str) -> bool: ...


class HMACSHA256Signer:
    """Reference signer using an injected secret; no secret is stored in source."""

    algorithm = "HMAC-SHA256"

    def __init__(self, key_id: str, secret: bytes) -> None:
        if not key_id.strip() or not secret:
            raise ValueError("key_id and secret are required")
        self.key_id = key_id
        self._secret = bytes(secret)

    def sign(self, message: bytes) -> str:
        return hmac.new(self._secret, message, "sha256").hexdigest()

    def verify(self, message: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign(message), signature)


def sign_admission(identity: ExecutionIdentity, signer: AdmissionSigner) -> SignedAdmissionArtifact:
    digest = identity.digest()
    return SignedAdmissionArtifact(identity, digest, signer.key_id, signer.algorithm, signer.sign(digest.encode("ascii")))


def verify_admission(artifact: SignedAdmissionArtifact, signer: AdmissionSigner) -> bool:
    if artifact.key_id != signer.key_id or artifact.algorithm != signer.algorithm:
        return False
    if artifact.identity_digest != artifact.identity.digest():
        return False
    return signer.verify(artifact.identity_digest.encode("ascii"), artifact.signature)


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    identity_digest: str
    attempt_id: UUID
    device_id: str
    sequence: int
    timestamp_ns: int
    result_digest: str
    admission_signature: str

    def __post_init__(self) -> None:
        for name, value in (("identity_digest", self.identity_digest), ("device_id", self.device_id), ("result_digest", self.result_digest), ("admission_signature", self.admission_signature)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.attempt_id, UUID):
            raise ValueError("attempt_id must be a UUID")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        if isinstance(self.timestamp_ns, bool) or not isinstance(self.timestamp_ns, int) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a nonnegative integer")


@dataclass(frozen=True, slots=True, init=False)
class DurableReceipt:
    identity_digest: str
    attempt_id: UUID
    sequence: int
    result_digest: str
    receipt_digest: str

    def __init__(self, identity_digest: str, attempt_id: UUID, sequence: int, result_digest: str, receipt_digest: str, *, _provenance_token: object | None = None) -> None:
        if _provenance_token is not _RECEIPT_FACTORY_TOKEN:
            raise PermissionError("durable receipt must originate from verified evidence")
        if not isinstance(identity_digest, str) or not identity_digest.strip():
            raise ValueError("identity_digest is required")
        if not isinstance(attempt_id, UUID):
            raise ValueError("attempt_id must be a UUID")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        if not isinstance(result_digest, str) or not result_digest.strip():
            raise ValueError("result_digest is required")
        if not isinstance(receipt_digest, str) or not receipt_digest.strip():
            raise ValueError("receipt_digest is required")
        if receipt_digest != self.compute_digest(identity_digest, attempt_id, sequence, result_digest):
            raise ValueError("receipt digest mismatch")
        object.__setattr__(self, "identity_digest", identity_digest)
        object.__setattr__(self, "attempt_id", attempt_id)
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(self, "result_digest", result_digest)
        object.__setattr__(self, "receipt_digest", receipt_digest)

    @staticmethod
    def compute_digest(identity_digest: str, attempt_id: UUID, sequence: int, result_digest: str) -> str:
        canonical = "|".join((identity_digest, str(attempt_id), str(sequence), result_digest))
        return sha256(canonical.encode("utf-8")).hexdigest()


class EvidenceStore(Protocol):
    """Atomic receipt persistence contract.

    Implementations must make the uniqueness check and insert one indivisible
    operation. A contains-then-record sequence is not sufficient under concurrency.
    """

    def commit_if_absent(self, receipt: DurableReceipt) -> bool: ...


class InMemoryEvidenceStore:
    """Process-local test/reference store; not durable across restarts."""

    def __init__(self) -> None:
        from threading import Lock

        self._receipts: dict[str, DurableReceipt] = {}
        self._lock = Lock()

    def contains(self, receipt_digest: str) -> bool:
        with self._lock:
            return receipt_digest in self._receipts

    def commit_if_absent(self, receipt: DurableReceipt) -> bool:
        with self._lock:
            if receipt.receipt_digest in self._receipts:
                return False
            self._receipts[receipt.receipt_digest] = receipt
            return True

    def record(self, receipt: DurableReceipt) -> None:
        if not self.commit_if_absent(receipt):
            raise ValueError("duplicate receipt replay")


class SQLiteEvidenceStore:
    """Durable SQLite receipt store with an atomic, unique receipt commit.

    The database file must live on storage whose durability and backup properties
    are appropriate for the deployment. This adapter does not provide remote
    replication, encryption-at-rest, key custody, or multi-host consensus.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS phase17_evidence_receipts (
            receipt_digest TEXT PRIMARY KEY,
            identity_digest TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence >= 0),
            result_digest TEXT NOT NULL
        )
    """

    def __init__(self, database_path: str, *, timeout_seconds: float = 5.0) -> None:
        import math
        import os
        import sqlite3

        if not isinstance(database_path, str) or not database_path.strip():
            raise ValueError("database_path must be a non-empty filesystem path")
        if database_path == ":memory:":
            raise ValueError("SQLiteEvidenceStore requires a persistent database file")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive finite number")
        self._database_path = os.fspath(database_path)
        self._timeout_seconds = float(timeout_seconds)
        with sqlite3.connect(self._database_path, timeout=self._timeout_seconds) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(self._SCHEMA)

    def contains(self, receipt_digest: str) -> bool:
        import sqlite3

        with sqlite3.connect(self._database_path, timeout=self._timeout_seconds) as connection:
            row = connection.execute(
                "SELECT 1 FROM phase17_evidence_receipts WHERE receipt_digest = ?",
                (receipt_digest,),
            ).fetchone()
            return row is not None

    def commit_if_absent(self, receipt: DurableReceipt) -> bool:
        import sqlite3

        if not isinstance(receipt, DurableReceipt):
            raise TypeError("receipt must be a verified DurableReceipt")
        connection = sqlite3.connect(
            self._database_path, timeout=self._timeout_seconds, isolation_level=None
        )
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO phase17_evidence_receipts
                        (receipt_digest, identity_digest, attempt_id, sequence, result_digest)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        receipt.receipt_digest,
                        receipt.identity_digest,
                        str(receipt.attempt_id),
                        receipt.sequence,
                        receipt.result_digest,
                    ),
                )
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                return False
            connection.execute("COMMIT")
            return True
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def record(self, receipt: DurableReceipt) -> None:
        if not self.commit_if_absent(receipt):
            raise ValueError("duplicate receipt replay")


class EvidenceVerifier:
    """Fail-closed verifier for admission binding, evidence, and durable receipts."""

    def __init__(self, store: EvidenceStore) -> None:
        self._store = store

    def verify_evidence(self, admission: SignedAdmissionArtifact, evidence: ExecutionEvidence, signer: AdmissionSigner, *, expected_device_id: str) -> None:
        if not verify_admission(admission, signer):
            raise PermissionError("invalid admission signature")
        if evidence.identity_digest != admission.identity_digest:
            raise ValueError("evidence identity mismatch")
        if evidence.attempt_id != admission.identity.attempt_id:
            raise ValueError("evidence attempt identity mismatch")
        if evidence.admission_signature != admission.signature:
            raise ValueError("evidence admission binding mismatch")
        if evidence.device_id != expected_device_id:
            raise ValueError("evidence device identity mismatch")

    def commit_verified_evidence(self, admission: SignedAdmissionArtifact, evidence: ExecutionEvidence, signer: AdmissionSigner, *, expected_device_id: str) -> DurableReceipt:
        self.verify_evidence(admission, evidence, signer, expected_device_id=expected_device_id)
        return self._commit_receipt(evidence)

    def _commit_receipt(self, evidence: ExecutionEvidence) -> DurableReceipt:
        receipt_digest = DurableReceipt.compute_digest(evidence.identity_digest, evidence.attempt_id, evidence.sequence, evidence.result_digest)
        receipt = DurableReceipt(evidence.identity_digest, evidence.attempt_id, evidence.sequence, evidence.result_digest, receipt_digest, _provenance_token=_RECEIPT_FACTORY_TOKEN)
        if not self._store.commit_if_absent(receipt):
            raise ValueError("duplicate receipt replay")
        return receipt
