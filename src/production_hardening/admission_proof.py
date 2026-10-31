from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping
import json
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@dataclass(frozen=True, slots=True)
class AdmissionClaims:
    """Canonical, short-lived authority claims signed by the external HOARE service."""

    authority_id: str
    tenant_id: str
    project_id: str
    device_id: str
    attempt_id: str
    request_digest: str
    capability_id: str
    lease_id: str
    fence_id: str
    key_id: str
    issued_at: int
    expires_at: int
    decision: str = "ALLOW"

    def __post_init__(self) -> None:
        required = (
            self.authority_id, self.tenant_id, self.project_id, self.device_id,
            self.attempt_id, self.request_digest, self.capability_id, self.lease_id,
            self.fence_id, self.key_id,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("admission claim identity fields are required")
        for name, value in (("issued_at", self.issued_at), ("expires_at", self.expires_at)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.expires_at <= self.issued_at:
            raise ValueError("admission proof expiry must follow issue time")
        if self.decision != "ALLOW":
            raise ValueError("only ALLOW claims may carry execution authority")


@dataclass(frozen=True, slots=True)
class SignedAdmissionProof:
    claims: AdmissionClaims
    signature: bytes
    algorithm: str = "Ed25519"

    def __post_init__(self) -> None:
        if not isinstance(self.claims, AdmissionClaims):
            raise TypeError("proof requires AdmissionClaims")
        if not isinstance(self.signature, bytes) or len(self.signature) != 64:
            raise ValueError("Ed25519 signature must be 64 bytes")
        if self.algorithm != "Ed25519":
            raise ValueError("unsupported admission proof algorithm")


def canonical_claims(claims: AdmissionClaims) -> bytes:
    values = {
        "authority_id": claims.authority_id,
        "tenant_id": claims.tenant_id,
        "project_id": claims.project_id,
        "device_id": claims.device_id,
        "attempt_id": claims.attempt_id,
        "request_digest": claims.request_digest,
        "capability_id": claims.capability_id,
        "lease_id": claims.lease_id,
        "fence_id": claims.fence_id,
        "key_id": claims.key_id,
        "issued_at": claims.issued_at,
        "expires_at": claims.expires_at,
        "decision": claims.decision,
    }
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class AdmissionProofVerifier:
    """Verifies HOARE signatures using externally provisioned trusted public keys."""

    def verify(
        self,
        proof: SignedAdmissionProof,
        *,
        tenant_id: str,
        project_id: str,
        device_id: str,
        attempt_id: str,
        request_digest: str,
    ) -> AdmissionClaims:
        raise NotImplementedError


class Ed25519AdmissionProofVerifier(AdmissionProofVerifier):
    def __init__(
        self,
        trusted_public_keys: Mapping[str, bytes],
        *,
        clock: Callable[[], float] = time.time,
        max_lifetime_seconds: int = 60,
        clock_skew_seconds: int = 5,
    ) -> None:
        if not trusted_public_keys:
            raise ValueError("at least one trusted HOARE public key is required")
        if isinstance(max_lifetime_seconds, bool) or max_lifetime_seconds <= 0:
            raise ValueError("max_lifetime_seconds must be positive")
        if isinstance(clock_skew_seconds, bool) or clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds must be non-negative")
        self._keys: dict[str, Ed25519PublicKey] = {}
        for key_id, raw_key in trusted_public_keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("trusted key IDs must be non-empty strings")
            if not isinstance(raw_key, bytes) or len(raw_key) != 32:
                raise ValueError("Ed25519 public keys must be 32 raw bytes")
            self._keys[key_id] = Ed25519PublicKey.from_public_bytes(raw_key)
        self._clock = clock
        self._max_lifetime = max_lifetime_seconds
        self._clock_skew = clock_skew_seconds

    def verify(
        self,
        proof: SignedAdmissionProof,
        *,
        tenant_id: str,
        project_id: str,
        device_id: str,
        attempt_id: str,
        request_digest: str,
    ) -> AdmissionClaims:
        if not isinstance(proof, SignedAdmissionProof):
            raise PermissionError("a signed HOARE admission proof is required")
        claims = proof.claims
        key = self._keys.get(claims.key_id)
        if key is None:
            raise PermissionError("admission proof key is not trusted")
        now = self._clock()
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise PermissionError("verifier clock is invalid")
        if claims.issued_at > now + self._clock_skew:
            raise PermissionError("admission proof is not yet valid")
        if claims.expires_at <= now - self._clock_skew:
            raise PermissionError("admission proof has expired")
        if claims.expires_at - claims.issued_at > self._max_lifetime:
            raise PermissionError("admission proof lifetime exceeds policy")
        expected = (tenant_id, project_id, device_id, attempt_id, request_digest)
        actual = (
            claims.tenant_id, claims.project_id, claims.device_id,
            claims.attempt_id, claims.request_digest,
        )
        if actual != expected:
            raise PermissionError("admission proof is bound to a different execution request")
        try:
            key.verify(proof.signature, canonical_claims(claims))
        except InvalidSignature as exc:
            raise PermissionError("HOARE admission proof signature is invalid") from exc
        return claims


def sign_admission_claims(claims: AdmissionClaims, private_key: Ed25519PrivateKey) -> SignedAdmissionProof:
    """HOARE-side signing helper; production private keys must remain outside PHyAI."""
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("private_key must be an Ed25519PrivateKey")
    return SignedAdmissionProof(claims, private_key.sign(canonical_claims(claims)))
