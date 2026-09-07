from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedHoareClient
from src.production_hardening.phase17_evidence import (
    AdmissionSigner,
    ExecutionEvidence,
    ExecutionIdentity,
    EvidenceVerifier,
    SignedAdmissionArtifact,
    sign_admission,
)


@dataclass(frozen=True, slots=True)
class Phase16AdmissionEnvelope:
    """Typed handoff from Phase 16 governance to Phase 17 evidence."""

    command: ControlCommand
    artifact_hash: str
    policy_digest: str
    admission: GovernedAdmission

    def __post_init__(self) -> None:
        if not self.artifact_hash.strip() or not self.policy_digest.strip():
            raise ValueError("artifact_hash and policy_digest are required")
        if not self.admission.accepted:
            raise PermissionError("denied admission cannot enter Phase 17")
        if self.admission.attempt_id != self.command.attempt_id:
            raise ValueError("admission attempt identity mismatch")
        if not self.command.tenant_id or not self.command.project_id:
            raise ValueError("command tenant/project identity is required")


class Phase16To17Boundary:
    """Single construction path from governed admission to signed evidence identity."""

    def __init__(self, hoare_client: GovernedHoareClient, signer: AdmissionSigner, evidence_verifier: EvidenceVerifier) -> None:
        self._hoare_client = hoare_client
        self._signer = signer
        self._evidence_verifier = evidence_verifier

    def admit_and_sign(
        self,
        command: ControlCommand,
        artifact_hash: str,
        policy_context: Mapping[str, str],
        policy_digest: str,
    ) -> tuple[Phase16AdmissionEnvelope, SignedAdmissionArtifact]:
        admission = self._hoare_client.admit(command, artifact_hash, policy_context)
        envelope = Phase16AdmissionEnvelope(command, artifact_hash, policy_digest, admission)
        identity = ExecutionIdentity.from_governed_admission(command, artifact_hash, policy_digest, admission)
        artifact = sign_admission(identity, self._signer)
        return envelope, artifact

    def commit_evidence(
        self,
        envelope: Phase16AdmissionEnvelope,
        admission_artifact: SignedAdmissionArtifact,
        evidence: ExecutionEvidence,
        *,
        expected_device_id: str,
    ):
        if admission_artifact.identity.attempt_id != envelope.command.attempt_id:
            raise ValueError("signed admission attempt identity mismatch")
        if admission_artifact.identity.artifact_hash != envelope.artifact_hash:
            raise ValueError("signed admission artifact mismatch")
        if admission_artifact.identity.policy_digest != envelope.policy_digest:
            raise ValueError("signed admission policy mismatch")
        return self._evidence_verifier.commit_verified_evidence(
            admission_artifact,
            evidence,
            self._signer,
            expected_device_id=expected_device_id,
        )


def boundary_digest(envelope: Phase16AdmissionEnvelope, admission_artifact: SignedAdmissionArtifact) -> str:
    """Stable audit digest for the exact Phase 16 -> Phase 17 handoff."""
    canonical = "|".join(
        (
            envelope.command.tenant_id,
            envelope.command.project_id,
            str(envelope.command.command_id),
            str(envelope.command.attempt_id),
            envelope.artifact_hash,
            envelope.policy_digest,
            admission_artifact.identity_digest,
        )
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
