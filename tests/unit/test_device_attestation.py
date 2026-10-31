from uuid import uuid4

import pytest

from src.production_hardening.device_attestation import (
    DeviceAttestationVerifier,
    DeviceEvidenceAttestation,
    DeviceKeyRecord,
    HMACDeviceEvidenceSigner,
    InMemoryDeviceKeyRegistry,
    SQLiteDeviceChallengeStore,
    create_device_attestation,
    issue_device_challenge,
)
from src.production_hardening.phase17_evidence import ExecutionEvidence


def fixture(tmp_path, *, enabled=True):
    device_id = "edge-device-01"
    attempt_id = uuid4()
    secret = b"device-reference-secret-material-32-bytes-minimum"
    signer = HMACDeviceEvidenceSigner("device-key-01", secret)
    registry = InMemoryDeviceKeyRegistry((
        DeviceKeyRecord(device_id, signer.key_id, signer.algorithm, secret, enabled),
    ))
    store = SQLiteDeviceChallengeStore(str(tmp_path / "device-challenges.sqlite3"))
    challenge = issue_device_challenge(
        device_id, attempt_id, 7, now_ns=1_000, lifetime_ns=500
    )
    attestation = create_device_attestation(
        challenge, timestamp_ns=1_100, result_digest="sha256:result-7", signer=signer
    )
    evidence = ExecutionEvidence(
        "identity-digest", attempt_id, device_id, 7, 1_100,
        "sha256:result-7", "governance-admission-signature",
    )
    return DeviceAttestationVerifier(registry, store), challenge, attestation, evidence


def test_device_attestation_binds_device_attempt_sequence_and_result(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    verifier.verify(challenge, attestation, evidence, now_ns=1_200)


def test_device_attestation_rejects_replay(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    verifier.verify(challenge, attestation, evidence, now_ns=1_200)
    with pytest.raises(PermissionError, match="replay"):
        verifier.verify(challenge, attestation, evidence, now_ns=1_200)


def test_device_attestation_rejects_wrong_device_evidence(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    wrong = ExecutionEvidence(
        evidence.identity_digest, evidence.attempt_id, "other-device",
        evidence.sequence, evidence.timestamp_ns, evidence.result_digest,
        evidence.admission_signature,
    )
    with pytest.raises(ValueError, match="execution evidence"):
        verifier.verify(challenge, attestation, wrong, now_ns=1_200)


def test_device_attestation_rejects_wrong_result_digest(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    wrong = ExecutionEvidence(
        evidence.identity_digest, evidence.attempt_id, evidence.device_id,
        evidence.sequence, evidence.timestamp_ns, "tampered-result",
        evidence.admission_signature,
    )
    with pytest.raises(ValueError, match="execution evidence"):
        verifier.verify(challenge, attestation, wrong, now_ns=1_200)


def test_device_attestation_rejects_signature_tampering(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    tampered = DeviceEvidenceAttestation(
        attestation.device_id, attestation.attempt_id, attestation.sequence,
        attestation.timestamp_ns, attestation.result_digest, attestation.nonce,
        attestation.key_id, attestation.algorithm, "00" * 32,
    )
    with pytest.raises(PermissionError, match="signature"):
        verifier.verify(challenge, tampered, evidence, now_ns=1_200)


def test_device_attestation_rejects_expired_challenge(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    with pytest.raises(PermissionError, match="not currently valid"):
        verifier.verify(challenge, attestation, evidence, now_ns=1_500)


def test_device_attestation_rejects_unregistered_or_disabled_device_key(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path, enabled=False)
    with pytest.raises(PermissionError, match="not registered or is disabled"):
        verifier.verify(challenge, attestation, evidence, now_ns=1_200)


def test_device_attestation_rejects_attestation_for_another_sequence(tmp_path):
    verifier, challenge, attestation, evidence = fixture(tmp_path)
    tampered = DeviceEvidenceAttestation(
        attestation.device_id, attestation.attempt_id, attestation.sequence + 1,
        attestation.timestamp_ns, attestation.result_digest, attestation.nonce,
        attestation.key_id, attestation.algorithm, attestation.signature,
    )
    with pytest.raises(ValueError, match="does not match challenge"):
        verifier.verify(challenge, tampered, evidence, now_ns=1_200)


def test_device_challenge_store_survives_reopen_and_rejects_nonce_reuse(tmp_path):
    path = str(tmp_path / "reopen.sqlite3")
    first = SQLiteDeviceChallengeStore(path)
    assert first.consume_once("nonce-1", "binding-1")
    reopened = SQLiteDeviceChallengeStore(path)
    assert not reopened.consume_once("nonce-1", "binding-1")


def test_device_challenge_store_rejects_memory_database():
    with pytest.raises(ValueError, match="persistent filesystem path"):
        SQLiteDeviceChallengeStore(":memory:")


def test_phase17_commit_requires_both_governance_and_device_verification(tmp_path):
    from datetime import datetime, timezone
    from src.phase1_contracts.contracts import ControlCommand
    from src.production_hardening.phase16_hoare_integration import (
        GovernedHoareClient, TransportAdmission,
    )
    from src.production_hardening.phase17_evidence import (
        EvidenceVerifier, HMACSHA256Signer, InMemoryEvidenceStore,
        ExecutionIdentity, sign_admission,
    )

    command = ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(),
        attempt_id=uuid4(), sequence=7, proposed_at=datetime.now(timezone.utc),
        target_id="edge-device-01", command_type="observe", parameters={"mode": 1},
        confidence=0.99, safety_precondition_ids=("safe-1",), scene_id=uuid4(),
        source_observation_ids=(uuid4(),), provenance_uri="urn:test", schema_version="v1",
    )
    context = {
        "tenant_id": "tenant-a", "project_id": "project-a",
        "policy_digest": "policy-a",
    }
    artifact_hash = "artifact-a"

    class Transport:
        def admit(self, request):
            return TransportAdmission(
                accepted=True, attempt_id=request.command.attempt_id,
                capability_id="cap-a", lease_id="lease-a", fence_id="fence-a",
                reason="accepted", request_digest=request.request_digest,
            )

    admission_response = GovernedHoareClient(Transport()).admit(
        command, artifact_hash, context
    )
    identity = ExecutionIdentity.from_governed_admission(
        command, artifact_hash, "policy-a", admission_response,
        policy_context=context,
    )
    governance_signer = HMACSHA256Signer("governance-key", b"governance-secret-32-bytes-minimum")
    signed_admission = sign_admission(identity, governance_signer)

    device_secret = b"device-secret-material-at-least-32-bytes"
    device_signer = HMACDeviceEvidenceSigner("device-key", device_secret)
    challenge = issue_device_challenge(
        "edge-device-01", command.attempt_id, 7, now_ns=2_000, lifetime_ns=500
    )
    device_attestation = create_device_attestation(
        challenge, timestamp_ns=2_100, result_digest="result-digest",
        signer=device_signer,
    )
    evidence = ExecutionEvidence(
        signed_admission.identity_digest, command.attempt_id, "edge-device-01",
        7, 2_100, "result-digest", signed_admission.signature,
    )
    registry = InMemoryDeviceKeyRegistry((
        DeviceKeyRecord("edge-device-01", "device-key", "HMAC-SHA256", device_secret),
    ))
    device_verifier = DeviceAttestationVerifier(
        registry, SQLiteDeviceChallengeStore(str(tmp_path / "combined.sqlite3"))
    )
    store = InMemoryEvidenceStore()
    verifier = EvidenceVerifier(store)
    receipt = verifier.commit_verified_evidence_with_device_attestation(
        signed_admission, evidence, governance_signer,
        expected_device_id="edge-device-01", challenge=challenge,
        attestation=device_attestation,
        device_attestation_verifier=device_verifier, now_ns=2_200,
    )
    assert store.contains(receipt.receipt_digest)


def test_combined_commit_does_not_persist_when_device_attestation_fails(tmp_path):
    from datetime import datetime, timezone
    from src.phase1_contracts.contracts import ControlCommand
    from src.production_hardening.phase16_hoare_integration import (
        GovernedHoareClient, TransportAdmission,
    )
    from src.production_hardening.phase17_evidence import (
        EvidenceVerifier, HMACSHA256Signer, InMemoryEvidenceStore,
        ExecutionIdentity, sign_admission,
    )

    command = ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(),
        attempt_id=uuid4(), sequence=3, proposed_at=datetime.now(timezone.utc),
        target_id="edge-device-02", command_type="observe", parameters={"mode": 1},
        confidence=0.99, safety_precondition_ids=("safe-1",), scene_id=uuid4(),
        source_observation_ids=(uuid4(),), provenance_uri="urn:test", schema_version="v1",
    )
    context = {"tenant_id": "tenant-a", "project_id": "project-a", "policy_digest": "policy-a"}

    class Transport:
        def admit(self, request):
            return TransportAdmission(
                accepted=True, attempt_id=request.command.attempt_id,
                capability_id="cap-a", lease_id="lease-a", fence_id="fence-a",
                reason="accepted", request_digest=request.request_digest,
            )

    governed = GovernedHoareClient(Transport()).admit(command, "artifact-a", context)
    identity = ExecutionIdentity.from_governed_admission(
        command, "artifact-a", "policy-a", governed, policy_context=context
    )
    governance_signer = HMACSHA256Signer("governance-key", b"governance-secret-32-bytes-minimum")
    signed = sign_admission(identity, governance_signer)
    evidence = ExecutionEvidence(
        signed.identity_digest, command.attempt_id, "edge-device-02", 3, 3_100,
        "actual-result", signed.signature,
    )
    challenge = issue_device_challenge(
        "edge-device-02", command.attempt_id, 3, now_ns=3_000, lifetime_ns=500
    )
    wrong_device_secret = b"wrong-device-secret-material-at-least-32-bytes"
    wrong_signer = HMACDeviceEvidenceSigner("device-key", wrong_device_secret)
    attestation = create_device_attestation(
        challenge, timestamp_ns=3_100, result_digest="forged-result",
        signer=wrong_signer,
    )
    registry = InMemoryDeviceKeyRegistry((
        DeviceKeyRecord("edge-device-02", "device-key", "HMAC-SHA256",
                        b"registered-device-secret-at-least-32-bytes"),
    ))
    device_verifier = DeviceAttestationVerifier(
        registry, SQLiteDeviceChallengeStore(str(tmp_path / "failed-combined.sqlite3"))
    )
    store = InMemoryEvidenceStore()
    with pytest.raises(ValueError, match="execution evidence"):
        EvidenceVerifier(store).commit_verified_evidence_with_device_attestation(
            signed, evidence, governance_signer,
            expected_device_id="edge-device-02", challenge=challenge,
            attestation=attestation,
            device_attestation_verifier=device_verifier, now_ns=3_200,
        )
    assert not store.contains(
        __import__("src.production_hardening.phase17_evidence", fromlist=["DurableReceipt"])
        .DurableReceipt.compute_digest(
            evidence.identity_digest, evidence.attempt_id, evidence.sequence,
            evidence.result_digest,
        )
    )
