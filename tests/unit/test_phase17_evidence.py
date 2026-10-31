from dataclasses import replace
from uuid import uuid4
from datetime import datetime, timezone

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import GovernedHoareClient, TransportAdmission
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


class FakeTransport:
    def __init__(self, response):
        self.response = response

    def admit(self, request):
        return self.response(request)


def command():
    return ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=uuid4(), sequence=1,
        proposed_at=datetime.now(timezone.utc), target_id="arm-1", command_type="position", parameters={"x": 0.1},
        confidence=0.95, safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )


def context():
    return {"tenant_id": "tenant-a", "project_id": "project-a", "policy_digest": "policy-123"}


def client_admission(cmd, artifact="artifact-123", *, accepted=True):
    ctx = context()

    def respond(request):
        if not accepted:
            return TransportAdmission(False, request.command.attempt_id, None, None, None, "denied")
        return TransportAdmission(
            True, request.command.attempt_id, "cap-1", "lease-1", "fence-1", "admitted",
            request.request_digest,
        )

    return GovernedHoareClient(FakeTransport(respond)).admit(cmd, artifact, ctx)


def governed_identity():
    cmd = command()
    admission = client_admission(cmd)
    return ExecutionIdentity.from_governed_admission(
        cmd, "artifact-123", "policy-123", admission, policy_context=context()
    )


def test_identity_digest_is_deterministic():
    item = governed_identity()
    assert item.digest() == item.digest() and len(item.digest()) == 64
    assert item.request_digest


def test_direct_identity_construction_is_sealed():
    with pytest.raises(PermissionError, match="must originate from governed admission"):
        ExecutionIdentity("tenant-a", "project-a", uuid4(), uuid4(), "artifact-123", "cap-1", "lease-1", "fence-1", "policy-123")


def test_identity_must_derive_authority_from_phase16_admission():
    cmd = command()
    denied = client_admission(cmd, accepted=False)
    with pytest.raises(PermissionError, match="denied admission"):
        ExecutionIdentity.from_governed_admission(
            cmd, "artifact-123", "policy-123", denied, policy_context=context()
        )
    admitted = client_admission(cmd)
    item = ExecutionIdentity.from_governed_admission(
        cmd, "artifact-123", "policy-123", admitted, policy_context=context()
    )
    assert item.attempt_id == cmd.attempt_id
    assert item.capability_id == "cap-1"


def test_identity_factory_rejects_admission_for_different_command():
    original = command()
    admission = client_admission(original)
    altered = replace(original, parameters={"x": 0.9})

    with pytest.raises(ValueError, match="request digest"):
        ExecutionIdentity.from_governed_admission(
            altered, "artifact-123", "policy-123", admission,
            policy_context=context(),
        )


def test_signed_admission_verifies_with_matching_key():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    artifact = sign_admission(governed_identity(), signer)
    assert verify_admission(artifact, signer)


def test_tampered_identity_fails_signature_verification():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    artifact = sign_admission(governed_identity(), signer)
    tampered_cmd = command()
    tampered = ExecutionIdentity.from_governed_admission(
        tampered_cmd, "different-artifact", "policy-123",
        client_admission(tampered_cmd, "different-artifact"),
        policy_context=context(),
    )
    with pytest.raises(ValueError, match="identity digest"):
        type(artifact)(tampered, artifact.identity_digest, artifact.key_id, artifact.algorithm, artifact.signature)


def test_wrong_key_fails_closed():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    other = HMACSHA256Signer("key-2", b"other-secret")
    assert not verify_admission(sign_admission(governed_identity(), signer), other)


def test_evidence_binds_admission_and_attempt():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(governed_identity(), signer)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result-1", admission.signature)
    verifier.verify_evidence(admission, evidence, signer, expected_device_id="jetson-1")
    rebound = ExecutionEvidence(admission.identity_digest, uuid4(), "jetson-1", 1, 10, "result-1", admission.signature)
    with pytest.raises(ValueError, match="attempt identity"):
        verifier.verify_evidence(admission, rebound, signer, expected_device_id="jetson-1")


def test_evidence_device_binding_is_fail_closed():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    admission = sign_admission(governed_identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result", admission.signature)
    with pytest.raises(ValueError, match="device identity"):
        EvidenceVerifier(InMemoryEvidenceStore()).verify_evidence(admission, evidence, signer, expected_device_id="jetson-2")


def test_direct_receipt_construction_is_sealed():
    digest = DurableReceipt.compute_digest("identity", uuid4(), 1, "result")
    with pytest.raises(PermissionError, match="must originate from verified evidence"):
        DurableReceipt("identity", uuid4(), 1, "result", digest)


def test_verified_evidence_is_required_for_commit_path():
    signer = HMACSHA256Signer("key-1", b"test-secret")
    other = HMACSHA256Signer("key-2", b"other-secret")
    admission = sign_admission(governed_identity(), signer)
    evidence = ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, "result", admission.signature)
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    with pytest.raises(PermissionError, match="invalid admission signature"):
        verifier.commit_verified_evidence(admission, evidence, other, expected_device_id="jetson-1")
    receipt = verifier.commit_verified_evidence(admission, evidence, signer, expected_device_id="jetson-1")
    assert receipt.receipt_digest == DurableReceipt.compute_digest(admission.identity_digest, admission.identity.attempt_id, 1, "result")
    with pytest.raises(ValueError, match="duplicate receipt replay"):
        verifier.commit_verified_evidence(admission, evidence, signer, expected_device_id="jetson-1")



@pytest.mark.parametrize("sequence", [True, -1, 1.5, "2"])
def test_execution_evidence_rejects_invalid_sequence_types(sequence):
    admission = sign_admission(governed_identity(), HMACSHA256Signer("key-1", b"secret"))
    with pytest.raises(ValueError, match="sequence"):
        ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", sequence, 10, "result", admission.signature)


@pytest.mark.parametrize("timestamp_ns", [True, -1, 1.5, "10"])
def test_execution_evidence_rejects_invalid_timestamp_types(timestamp_ns):
    admission = sign_admission(governed_identity(), HMACSHA256Signer("key-1", b"secret"))
    with pytest.raises(ValueError, match="timestamp_ns"):
        ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, timestamp_ns, "result", admission.signature)


def test_execution_evidence_requires_uuid_attempt_and_string_digests():
    admission = sign_admission(governed_identity(), HMACSHA256Signer("key-1", b"secret"))
    with pytest.raises(ValueError, match="attempt_id"):
        ExecutionEvidence(admission.identity_digest, "not-a-uuid", "jetson-1", 1, 10, "result", admission.signature)
    with pytest.raises(ValueError, match="result_digest"):
        ExecutionEvidence(admission.identity_digest, admission.identity.attempt_id, "jetson-1", 1, 10, 123, admission.signature)


@pytest.mark.parametrize("sequence", [True, -1, 1.5, "2"])
def test_receipt_factory_rejects_invalid_sequence_types(sequence):
    from src.production_hardening import phase17_evidence as evidence_module
    attempt = uuid4()
    digest = DurableReceipt.compute_digest("identity", attempt, sequence, "result")
    with pytest.raises(ValueError, match="sequence"):
        DurableReceipt("identity", attempt, sequence, "result", digest, _provenance_token=evidence_module._RECEIPT_FACTORY_TOKEN)


def test_receipt_factory_rejects_invalid_identity_fields():
    from src.production_hardening import phase17_evidence as evidence_module
    attempt = uuid4()
    digest = DurableReceipt.compute_digest("identity", attempt, 1, "result")
    with pytest.raises(ValueError, match="attempt_id"):
        DurableReceipt("identity", "not-a-uuid", 1, "result", digest, _provenance_token=evidence_module._RECEIPT_FACTORY_TOKEN)
    with pytest.raises(ValueError, match="result_digest"):
        DurableReceipt("identity", attempt, 1, "", digest, _provenance_token=evidence_module._RECEIPT_FACTORY_TOKEN)



def test_sqlite_evidence_store_persists_receipts_across_reopen(tmp_path):
    from src.production_hardening.phase17_evidence import SQLiteEvidenceStore

    signer = HMACSHA256Signer("key-1", b"persistent-test-secret")
    admission = sign_admission(governed_identity(), signer)
    evidence = ExecutionEvidence(
        admission.identity_digest, admission.identity.attempt_id,
        "jetson-1", 1, 10, "persistent-result", admission.signature,
    )
    database_path = str(tmp_path / "phase17-evidence.sqlite3")
    first_store = SQLiteEvidenceStore(database_path)
    receipt = EvidenceVerifier(first_store).commit_verified_evidence(
        admission, evidence, signer, expected_device_id="jetson-1"
    )
    assert first_store.contains(receipt.receipt_digest)

    reopened_store = SQLiteEvidenceStore(database_path)
    assert reopened_store.contains(receipt.receipt_digest)
    with pytest.raises(ValueError, match="duplicate receipt replay"):
        EvidenceVerifier(reopened_store).commit_verified_evidence(
            admission, evidence, signer, expected_device_id="jetson-1"
        )


def test_sqlite_evidence_store_commits_duplicate_receipt_atomically(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from src.production_hardening.phase17_evidence import SQLiteEvidenceStore

    signer = HMACSHA256Signer("key-1", b"concurrency-test-secret")
    admission = sign_admission(governed_identity(), signer)
    evidence = ExecutionEvidence(
        admission.identity_digest, admission.identity.attempt_id,
        "jetson-1", 7, 70, "concurrent-result", admission.signature,
    )
    store = SQLiteEvidenceStore(str(tmp_path / "phase17-concurrency.sqlite3"))
    verifier = EvidenceVerifier(store)

    def commit_once():
        try:
            verifier.commit_verified_evidence(
                admission, evidence, signer, expected_device_id="jetson-1"
            )
            return "committed"
        except ValueError as exc:
            if "duplicate receipt replay" in str(exc):
                return "duplicate"
            raise

    with ThreadPoolExecutor(max_workers=12) as executor:
        outcomes = list(executor.map(lambda _: commit_once(), range(24)))

    assert outcomes.count("committed") == 1
    assert outcomes.count("duplicate") == 23


@pytest.mark.parametrize("timeout_seconds", [True, 0, -1, float("nan"), float("inf")])
def test_sqlite_evidence_store_rejects_invalid_timeout(tmp_path, timeout_seconds):
    from src.production_hardening.phase17_evidence import SQLiteEvidenceStore

    with pytest.raises(ValueError, match="timeout_seconds"):
        SQLiteEvidenceStore(str(tmp_path / "invalid-timeout.sqlite3"), timeout_seconds=timeout_seconds)


def test_sqlite_evidence_store_rejects_in_memory_database():
    from src.production_hardening.phase17_evidence import SQLiteEvidenceStore

    with pytest.raises(ValueError, match="persistent database file"):
        SQLiteEvidenceStore(":memory:")
