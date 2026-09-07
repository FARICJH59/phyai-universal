from uuid import uuid4
from datetime import datetime, timezone

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import GovernedAdmission
from src.production_hardening.phase17_evidence import (
    DurableReceipt,
    ExecutionEvidence,
    ExecutionIdentity,
    EvidenceVerifier,
    HMACSHA256Signer,
    InMemoryEvidenceStore,
    sign_admission,
    verify_admission,
)


def identity():
    return ExecutionIdentity("tenant-a", "project-a", uuid4(), uuid4(), "artifact-123", "cap-1", "lease-1", "fence-1", "policy-123")


def command():
    return ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=uuid4(), sequence=1,
        proposed_at=datetime.now(timezone.utc), target_id="arm-1", command_type="position", parameters={"x": 0.1},
        confidence=0.95, safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )


def test_identity_digest_is_deterministic():
    item = identity()
    assert item.digest() == item.digest() and len(item.digest()) == 64


def test_identity_must_derive_authority_from_phase16_admission():
    cmd = command()
    denied = GovernedAdmission(False, cmd.attempt_id, None, None, None, "denied")
    with pytest.raises(PermissionError, match="denied admission"):
        ExecutionIdentity.from_governed_admission(cmd, "artifact", "policy", denied)
    admitted = GovernedAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")
    item = ExecutionIdentity.from_governed_admission(cmd, "artifact", "policy", admitted)
    assert item.attempt_id == cmd.attempt_id
    assert item.capability_id == "cap-1"


def test_signed_admission_verifies_with_matching_key():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    artifact = sign_admission(identity(), signer)
    assert verify_admission(artifact, signer)


def test_tampered_identity_fails_signature_verification():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    artifact = sign_admission(identity(), signer)
    tampered = ExecutionIdentity(artifact.identity.tenant_id, artifact.identity.project_id, artifact.identity.command_id, artifact.identity.attempt_id, "different-artifact", artifact.identity.capability_id, artifact.identity.lease_id, artifact.identity.fence_id, artifact.identity.policy_digest)
    with pytest.raises(ValueError, match="identity digest"):
        type(artifact)(tampered, artifact.identity_digest, artifact.key_id, artifact.algorithm, artifact.signature)


def test_wrong_key_fails_closed():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    other = HMACSHA256Signer("key-2", b"other-secret")
    assert not verify_admission(sign_admission(identity(), signer), other)


def test_evidence_binds_admission_and_attempt():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(identity(), signer)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result-1", admission.signature)
    verifier.verify_evidence(admission, evidence, signer, expected_device_id="jetson-1")
    rebound = ExecutionEvidence(admission.identity_digest, uuid4(), "jetson-1", 1, 10, "result-1", admission.signature)
    with pytest.raises(ValueError, match="attempt identity"):
        verifier.verify_evidence(admission, rebound, signer, expected_device_id="jetson-1")


def test_evidence_device_binding_is_fail_closed():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result", admission.signature)
    with pytest.raises(ValueError, match="device identity"):
        EvidenceVerifier(InMemoryEvidenceStore()).verify_evidence(admission, evidence, signer, expected_device_id="jetson-2")


def test_verified_evidence_is_required_for_commit_path():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    other = HMACSHA256Signer("key-2", b"other-secret")
    admission = sign_admission(identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result", admission.signature)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    with pytest.raises(PermissionError, match="invalid admission signature"):
        verifier.commit_verified_evidence(admission, evidence, other, expected_device_id="jetson-1")
    receipt = verifier.commit_verified_evidence(admission, evidence, signer, expected_device_id="jetson-1")
    assert receipt.receipt_digest == DurableReceipt.compute_digest(admission.identity_digest, admission.identity.attempt_id, 1, "result")
    with pytest.raises(ValueError, match="duplicate receipt replay"):
        verifier.commit_verified_evidence(admission, evidence, signer, expected_device_id="jetson-1")
