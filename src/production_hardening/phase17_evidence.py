from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
from typing import Protocol
from uuid import UUID

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import GovernedAdmission


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    """Immutable identity binding for one governed execution attempt."""

    tenant_id: str
    project_id: str
    command_id: UUID
    attempt_id: UUID
    artifact_hash: str
    capability_id: str
    lease_id: str
    fence_id: str
    policy_digest: str

    def __post_init__(self) -> None:
        for name, value in (("tenant_id", self.tenant_id), ("project_id", self.project_id), ("artifact_hash", self.artifact_hash), ("capability_id", self.capability_id), ("lease_id", self.lease_id), ("fence_id", self.fence_id), ("policy_digest", self.policy_digest)):
            if not value.strip():
                raise ValueError(f"{name} is required")

    def canonical(self) -> str:
        return "|".join((self.tenant_id, self.project_id, str(self.command_id), str(self.attempt_id), self.artifact_hash, self.capability_id, self.lease_id, self.fence_id, self.policy_digest))

    def digest(self) -> str:
        return sha256(self.canonical().encode("utf-8")).hexdigest()

    @classmethod
    def from_governed_admission(cls, command: ControlCommand, artifact_hash: str, policy_digest: str, admission: GovernedAdmission) -> "ExecutionIdentity":
        if not admission.accepted:
            raise PermissionError("cannot create execution identity from denied admission")
        if admission.attempt_id != command.attempt_id:
            raise ValueError("governed admission attempt identity mismatch")
        if not admission.capability_id or not admission.lease_id or not admission.fence_id:
            raise ValueError("accepted admission is missing authority")
        return cls(command.tenant_id, command.project_id, command.command_id, admission.attempt_id, artifact_hash, admission.capability_id, admission.lease_id, admission.fence_id, policy_digest)


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
            if not value.strip():
                raise ValueError(f"{name} is required")
        if self.sequence < 0 or self.timestamp_ns < 0:
            raise ValueError("sequence and timestamp_ns must be nonnegative")


@dataclass(frozen=True, slots=True)
class DurableReceipt:
    identity_digest: str
    attempt_id: UUID
    sequence: int
    result_digest: str
    receipt_digest: str

    def __post_init__(self) -> None:
        if self.receipt_digest != self.compute_digest(self.identity_digest, self.attempt_id, self.sequence, self.result_digest):
            raise ValueError("receipt digest mismatch")

    @staticmethod
    def compute_digest(identity_digest: str, attempt_id: UUID, sequence: int, result_digest: str) -> str:
        canonical = "|".join((identity_digest, str(attempt_id), str(sequence), result_digest))
        return sha256(canonical.encode("utf-8")).hexdigest()


class EvidenceStore(Protocol):
    def contains(self, receipt_digest: str) -> bool: ...
    def record(self, receipt: DurableReceipt) -> None: ...


class InMemoryEvidenceStore:
    def __init__(self) -> None:
        self._receipts: dict[str, DurableReceipt] = {}

    def contains(self, receipt_digest: str) -> bool:
        return receipt_digest in self._receipts

    def record(self, receipt: DurableReceipt) -> None:
        if self.contains(receipt.receipt_digest):
            raise ValueError("duplicate receipt replay")
        self._receipts[receipt.receipt_digest] = receipt


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
        """Internal-only receipt commit; callers must enter through verified evidence."""
        receipt_digest = DurableReceipt.compute_digest(evidence.identity_digest, evidence.attempt_id, evidence.sequence, evidence.result_digest)
        receipt = DurableReceipt(evidence.identity_digest, evidence.attempt_id, evidence.sequence, evidence.result_digest, receipt_digest)
        if self._store.contains(receipt.receipt_digest):
            raise ValueError("duplicate receipt replay")
        self._store.record(receipt)
        return receipt
