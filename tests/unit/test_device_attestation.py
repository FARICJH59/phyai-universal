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
