from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_17_boundary import Phase16To17Boundary, boundary_digest
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedHoareClient
from src.production_hardening.phase17_evidence import ExecutionEvidence, EvidenceVerifier, HMACSHA256Signer, InMemoryEvidenceStore


class FakeTransport:
    def __init__(self, admission):
        self.admission = admission

    def admit(self, request):
        return self.admission


def command():
    return ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=uuid4(),
        sequence=1, proposed_at=datetime.now(timezone.utc), target_id="arm-1",
        command_type="position", parameters={"x": 0.1}, confidence=0.95,
        safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )


def test_boundary_only_signs_accepted_phase16_admission():
    cmd = command()
    admission = GovernedAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")
    boundary = Phase16To17Boundary(
        GovernedHoareClient(FakeTransport(admission)),
        HMACSHA256Signer("key-1", b"secret"),
        EvidenceVerifier(InMemoryEvidenceStore()),
    )
    envelope, signed = boundary.admit_and_sign(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"}, "policy")
    assert envelope.admission is admission
    assert signed.identity.attempt_id == cmd.attempt_id
    assert signed.identity.capability_id == "cap-1"
    assert signed.identity.lease_id == "lease-1"
    assert signed.identity.fence_id == "fence-1"


def test_denied_admission_cannot_cross_boundary():
    cmd = command()
    admission = GovernedAdmission(False, cmd.attempt_id, None, None, None, "denied")
    boundary = Phase16To17Boundary(
        GovernedHoareClient(FakeTransport(admission)),
        HMACSHA256Signer("key-1", b"secret"),
        EvidenceVerifier(InMemoryEvidenceStore()),
    )
    with pytest.raises(PermissionError, match="denied admission"):
        boundary.admit_and_sign(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"}, "policy")


def test_boundary_rejects_artifact_or_policy_rebinding():
    cmd = command()
    admission = GovernedAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")
    boundary = Phase16To17Boundary(
        GovernedHoareClient(FakeTransport(admission)),
        HMACSHA256Signer("key-1", b"secret"),
        EvidenceVerifier(InMemoryEvidenceStore()),
    )
    envelope, signed = boundary.admit_and_sign(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"}, "policy")
    evidence = ExecutionEvidence(signed.identity_digest, cmd.attempt_id, "device-1", 1, 10, "result", signed.signature)
    object.__setattr__(envelope, "artifact_hash", "different")
    with pytest.raises(ValueError, match="artifact mismatch"):
        boundary.commit_evidence(envelope, signed, evidence, expected_device_id="device-1")


def test_boundary_digest_is_stable_for_same_handoff():
    cmd = command()
    admission = GovernedAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")
    boundary = Phase16To17Boundary(
        GovernedHoareClient(FakeTransport(admission)),
        HMACSHA256Signer("key-1", b"secret"),
        EvidenceVerifier(InMemoryEvidenceStore()),
    )
    envelope, signed = boundary.admit_and_sign(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"}, "policy")
    assert boundary_digest(envelope, signed) == boundary_digest(envelope, signed)
