from uuid import uuid4

import pytest

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
    return ExecutionIdentity(
        tenant_id="tenant-a",
        project_id="project-a",
        command_id=uuid4(),
        attempt_id=uuid4(),
        artifact_hash="artifact-123",
        capability_id="cap-1",
        lease_id="lease-1",
        fence_id="fence-1",
        policy_digest="policy-123",
    )


def test_identity_digest_is_deterministic():
    item = identity()
    assert item.digest() == item.digest()
    assert len(item.digest()) == 64


def test_signed_admission_verifies_with_matching_key():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    artifact = sign_admission(identity(), signer)
    assert verify_admission(artifact, signer)


def test_tampered_identity_fails_signature_verification():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    artifact = sign_admission(identity(), signer)
    tampered = ExecutionIdentity(
        tenant_id=artifact.identity.tenant_id,
        project_id=artifact.identity.project_id,
        command_id=artifact.identity.command_id,
        attempt_id=artifact.identity.attempt_id,
        artifact_hash="different-artifact",
        capability_id=artifact.identity.capability_id,
        lease_id=artifact.identity.lease_id,
        fence_id=artifact.identity.fence_id,
        policy_digest=artifact.identity.policy_digest,
    )
    with pytest.raises(ValueError, match="identity digest"):
        type(artifact)(tampered, artifact.identity_digest, artifact.key_id, artifact.algorithm, artifact.signature)


def test_wrong_key_fails_closed():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    other = HMACSHA256Signer("key-2", b"other-secret")
    artifact = sign_admission(identity(), signer)
    assert not verify_admission(artifact, other)


def test_evidence_must_bind_capability_lease_fence_and_attempt():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(identity(), signer)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    evidence = ExecutionEvidence(
        identity_digest=admission.identity_digest,
        attempt_id=admission.identity.attempt_id,
        device_id="jetson-1",
        sequence=1,
        timestamp_ns=10,
        result_digest="result-1",
        admission_signature=admission.signature,
    )
    verifier.verify_evidence(admission, evidence, signer, expected_device_id="jetson-1")

    rebound = ExecutionEvidence(
        identity_digest=admission.identity_digest,
        attempt_id=uuid4(),
        device_id="jetson-1",
        sequence=1,
        timestamp_ns=10,
        result_digest="result-1",
        admission_signature=admission.signature,
    )
    with pytest.raises(ValueError, match="attempt identity"):
        verifier.verify_evidence(admission, rebound, signer, expected_device_id="jetson-1")


def test_evidence_device_binding_is_fail_closed():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result", admission.signature)
    with pytest.raises(ValueError, match="device identity"):
        EvidenceVerifier(InMemoryEvidenceStore()).verify_evidence(admission, evidence, signer, expected_device_id="jetson-2")


def test_receipt_is_content_addressed_and_replay_is_rejected():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 7, 20, "result-1", admission.signature)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    receipt = verifier.commit_receipt(evidence)
    assert receipt.receipt_digest == DurableReceipt.compute_digest(admission.identity_digest, admission.identity.attempt_id, 7, "result-1")
    with pytest.raises(ValueError, match="duplicate receipt replay"):
        verifier.commit_receipt(evidence)


def test_invalid_admission_signature_prevents_receipt_path():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    other = HMACSHA256Signer("key-2", b"other-secret")
    admission = sign_admission(identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result", admission.signature)
    with pytest.raises(PermissionError, match="invalid admission signature"):
        EvidenceVerifier(InMemoryEvidenceStore()).verify_evidence(admission, evidence, other, expected_device_id="jetson-1")
