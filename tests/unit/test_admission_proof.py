from dataclasses import replace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.production_hardening.admission_proof import (
    AdmissionClaims,
    Ed25519AdmissionProofVerifier,
    sign_admission_claims,
)


NOW = 1_800_000_000


def keys():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, public


def claims(**overrides):
    values = dict(
        authority_id="hoare-prod", tenant_id="tenant-a", project_id="project-a",
        device_id="edge-01", attempt_id="attempt-01", request_digest="a" * 64,
        capability_id="cap-01", lease_id="lease-01", fence_id="fence-01",
        key_id="hoare-key-2026-01", issued_at=NOW - 1, expires_at=NOW + 30,
    )
    values.update(overrides)
    return AdmissionClaims(**values)


def test_ed25519_proof_verifies_exact_bound_request():
    private, public = keys()
    proof = sign_admission_claims(claims(), private)
    verifier = Ed25519AdmissionProofVerifier({"hoare-key-2026-01": public}, clock=lambda: NOW)
    result = verifier.verify(
        proof, tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
        attempt_id="attempt-01", request_digest="a" * 64,
    )
    assert result.capability_id == "cap-01"


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "tenant-b"), ("project_id", "project-b"),
    ("device_id", "edge-02"), ("attempt_id", "attempt-02"),
    ("request_digest", "b" * 64),
])
def test_proof_rejects_request_rebinding(field, value):
    private, public = keys()
    proof = sign_admission_claims(claims(), private)
    verifier = Ed25519AdmissionProofVerifier({"hoare-key-2026-01": public}, clock=lambda: NOW)
    expected = dict(
        tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
        attempt_id="attempt-01", request_digest="a" * 64,
    )
    expected[field] = value
    with pytest.raises(PermissionError, match="different execution request"):
        verifier.verify(proof, **expected)


def test_proof_rejects_tampered_claims():
    private, public = keys()
    proof = sign_admission_claims(claims(), private)
    tampered = replace(proof, claims=replace(proof.claims, fence_id="fence-forged"))
    verifier = Ed25519AdmissionProofVerifier({"hoare-key-2026-01": public}, clock=lambda: NOW)
    with pytest.raises(PermissionError, match="signature is invalid"):
        verifier.verify(
            tampered, tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
            attempt_id="attempt-01", request_digest="a" * 64,
        )


def test_proof_rejects_unknown_key_and_expiry():
    private, public = keys()
    proof = sign_admission_claims(claims(), private)
    verifier = Ed25519AdmissionProofVerifier({"other-key": public}, clock=lambda: NOW)
    with pytest.raises(PermissionError, match="not trusted"):
        verifier.verify(
            proof, tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
            attempt_id="attempt-01", request_digest="a" * 64,
        )
    expired = sign_admission_claims(claims(issued_at=NOW - 40, expires_at=NOW - 10), private)
    verifier = Ed25519AdmissionProofVerifier({"hoare-key-2026-01": public}, clock=lambda: NOW)
    with pytest.raises(PermissionError, match="expired"):
        verifier.verify(
            expired, tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
            attempt_id="attempt-01", request_digest="a" * 64,
        )


def test_proof_rejects_overlong_lifetime_and_invalid_claim_times():
    with pytest.raises(ValueError, match="expiry"):
        claims(issued_at=NOW, expires_at=NOW)
    private, public = keys()
    proof = sign_admission_claims(claims(issued_at=NOW - 1, expires_at=NOW + 120), private)
    verifier = Ed25519AdmissionProofVerifier({"hoare-key-2026-01": public}, clock=lambda: NOW)
    with pytest.raises(PermissionError, match="lifetime"):
        verifier.verify(
            proof, tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
            attempt_id="attempt-01", request_digest="a" * 64,
        )
