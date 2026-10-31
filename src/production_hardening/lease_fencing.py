from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol
import json
import secrets
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


@dataclass(frozen=True, slots=True)
class LeaseFenceLookup:
    """Versioned public request contract for an authoritative HOARE lease lookup."""

    tenant_id: str
    project_id: str
    device_id: str
    capability_id: str
    lease_id: str
    fence_id: str
    nonce: str
    requested_at: int
    contract_version: str = "hoare.lease-fence.v1"

    def __post_init__(self) -> None:
        values = (
            self.tenant_id, self.project_id, self.device_id, self.capability_id,
            self.lease_id, self.fence_id, self.nonce, self.contract_version,
        )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("lease lookup identity, nonce, and version are required")
        if len(self.nonce) < 32:
            raise ValueError("lease lookup nonce must contain at least 32 characters")
        if isinstance(self.requested_at, bool) or not isinstance(self.requested_at, int) or self.requested_at < 0:
            raise ValueError("requested_at must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class SignedLeaseFenceStatus:
    """Public, signed status response; contains no proprietary lease implementation."""

    authority_id: str
    tenant_id: str
    project_id: str
    device_id: str
    capability_id: str
    lease_id: str
    fence_id: str
    current_fence_id: str
    lease_expires_at: int
    revoked: bool
    request_nonce: str
    issued_at: int
    response_expires_at: int
    key_id: str
    signature: bytes
    algorithm: str = "Ed25519"
    contract_version: str = "hoare.lease-fence.v1"

    def __post_init__(self) -> None:
        required = (
            self.authority_id, self.tenant_id, self.project_id, self.device_id,
            self.capability_id, self.lease_id, self.fence_id, self.current_fence_id,
            self.request_nonce, self.key_id, self.contract_version,
        )
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("signed lease status identity fields are required")
        for name, value in (
            ("lease_expires_at", self.lease_expires_at),
            ("issued_at", self.issued_at),
            ("response_expires_at", self.response_expires_at),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.response_expires_at <= self.issued_at:
            raise ValueError("response expiry must follow issue time")
        if not isinstance(self.revoked, bool):
            raise ValueError("revoked must be a boolean")
        if not isinstance(self.signature, bytes) or len(self.signature) != 64:
            raise ValueError("Ed25519 signature must be 64 bytes")
        if self.algorithm != "Ed25519":
            raise ValueError("unsupported lease status signature algorithm")


def canonical_lease_status(status: SignedLeaseFenceStatus) -> bytes:
    values = {
        "authority_id": status.authority_id,
        "tenant_id": status.tenant_id,
        "project_id": status.project_id,
        "device_id": status.device_id,
        "capability_id": status.capability_id,
        "lease_id": status.lease_id,
        "fence_id": status.fence_id,
        "current_fence_id": status.current_fence_id,
        "lease_expires_at": status.lease_expires_at,
        "revoked": status.revoked,
        "request_nonce": status.request_nonce,
        "issued_at": status.issued_at,
        "response_expires_at": status.response_expires_at,
        "key_id": status.key_id,
        "algorithm": status.algorithm,
        "contract_version": status.contract_version,
    }
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class HoareLeaseFenceTransport(Protocol):
    """Transport adapter supplied by the HOARE deployment; no endpoint is assumed."""

    def fetch_current(self, request: LeaseFenceLookup) -> SignedLeaseFenceStatus: ...


@dataclass(frozen=True, slots=True)
class LeaseFenceSnapshot:
    """Verified current lease/fence state safe to consume at the PHyAI boundary."""

    tenant_id: str
    project_id: str
    device_id: str
    capability_id: str
    lease_id: str
    fence_id: str
    current_fence_id: str
    lease_expires_at: int
    revoked: bool

    def __post_init__(self) -> None:
        identity = (
            self.tenant_id, self.project_id, self.device_id, self.capability_id,
            self.lease_id, self.fence_id, self.current_fence_id,
        )
        if any(not isinstance(value, str) or not value.strip() for value in identity):
            raise ValueError("lease/fence snapshot identity fields are required")
        if (
            isinstance(self.lease_expires_at, bool)
            or not isinstance(self.lease_expires_at, int)
            or self.lease_expires_at < 0
        ):
            raise ValueError("lease_expires_at must be a non-negative integer")
        if not isinstance(self.revoked, bool):
            raise ValueError("revoked must be a boolean")


class LeaseFenceVerifier:
    """Contract consumed by Phase 15; implementations must fail closed."""

    def validate_current(
        self,
        *,
        tenant_id: str,
        project_id: str,
        device_id: str,
        capability_id: str,
        lease_id: str,
        fence_id: str,
    ) -> LeaseFenceSnapshot:
        raise NotImplementedError("a live HOARE lease/fence verifier must be configured")


class HoareLeaseFenceAdapter(LeaseFenceVerifier):
    """Verifies nonce-bound HOARE lease status using provisioned public keys.

    The injected transport must use the deployment's authenticated, encrypted
    channel (for example mTLS) and must map the documented HOARE API to the
    versioned public request/response contracts above. This class intentionally
    does not guess a URL, endpoint, authentication scheme, or private-core API.
    """

    def __init__(
        self,
        transport: HoareLeaseFenceTransport,
        trusted_public_keys: Mapping[str, bytes],
        *,
        clock: Callable[[], float] = time.time,
        nonce_factory: Callable[[], str] = lambda: secrets.token_hex(32),
        max_response_age_seconds: int = 5,
        max_response_lifetime_seconds: int = 10,
        clock_skew_seconds: int = 2,
    ) -> None:
        if not trusted_public_keys:
            raise ValueError("at least one trusted HOARE lease-status public key is required")
        for name, value in (
            ("max_response_age_seconds", max_response_age_seconds),
            ("max_response_lifetime_seconds", max_response_lifetime_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if isinstance(clock_skew_seconds, bool) or not isinstance(clock_skew_seconds, int) or clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds must be non-negative")
        self._transport = transport
        self._keys: dict[str, Ed25519PublicKey] = {}
        for key_id, raw_key in trusted_public_keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("trusted key IDs must be non-empty strings")
            if not isinstance(raw_key, bytes) or len(raw_key) != 32:
                raise ValueError("Ed25519 public keys must be 32 raw bytes")
            self._keys[key_id] = Ed25519PublicKey.from_public_bytes(raw_key)
        self._clock = clock
        self._nonce_factory = nonce_factory
        self._max_age = max_response_age_seconds
        self._max_lifetime = max_response_lifetime_seconds
        self._skew = clock_skew_seconds

    def validate_current(
        self,
        *,
        tenant_id: str,
        project_id: str,
        device_id: str,
        capability_id: str,
        lease_id: str,
        fence_id: str,
    ) -> LeaseFenceSnapshot:
        now = self._clock()
        if isinstance(now, bool) or not isinstance(now, (int, float)) or now < 0:
            raise PermissionError("lease verifier clock is invalid")
        nonce = self._nonce_factory()
        request = LeaseFenceLookup(
            tenant_id=tenant_id,
            project_id=project_id,
            device_id=device_id,
            capability_id=capability_id,
            lease_id=lease_id,
            fence_id=fence_id,
            nonce=nonce,
            requested_at=int(now),
        )
        status = self._transport.fetch_current(request)
        if not isinstance(status, SignedLeaseFenceStatus):
            raise PermissionError("HOARE lease service returned an invalid status contract")
        key = self._keys.get(status.key_id)
        if key is None:
            raise PermissionError("HOARE lease status signing key is not trusted")
        expected_identity = (tenant_id, project_id, device_id, capability_id, lease_id, fence_id)
        actual_identity = (
            status.tenant_id, status.project_id, status.device_id,
            status.capability_id, status.lease_id, status.fence_id,
        )
        if actual_identity != expected_identity:
            raise PermissionError("HOARE lease status is bound to a different authority")
        if status.request_nonce != nonce:
            raise PermissionError("HOARE lease status nonce mismatch or replay detected")
        if status.contract_version != "hoare.lease-fence.v1":
            raise PermissionError("unsupported HOARE lease status contract version")
        if status.issued_at > now + self._skew:
            raise PermissionError("HOARE lease status is not yet valid")
        if status.issued_at < now - self._max_age - self._skew:
            raise PermissionError("HOARE lease status is stale")
        if status.response_expires_at <= now - self._skew:
            raise PermissionError("HOARE lease status response has expired")
        if status.response_expires_at - status.issued_at > self._max_lifetime:
            raise PermissionError("HOARE lease status response lifetime exceeds policy")
        try:
            key.verify(status.signature, canonical_lease_status(status))
        except InvalidSignature as exc:
            raise PermissionError("HOARE lease status signature is invalid") from exc
        return LeaseFenceSnapshot(
            tenant_id=status.tenant_id,
            project_id=status.project_id,
            device_id=status.device_id,
            capability_id=status.capability_id,
            lease_id=status.lease_id,
            fence_id=status.fence_id,
            current_fence_id=status.current_fence_id,
            lease_expires_at=status.lease_expires_at,
            revoked=status.revoked,
        )


def require_current_lease_fence(
    snapshot: LeaseFenceSnapshot,
    *,
    tenant_id: str,
    project_id: str,
    device_id: str,
    capability_id: str,
    lease_id: str,
    fence_id: str,
    now: float,
) -> None:
    if not isinstance(snapshot, LeaseFenceSnapshot):
        raise PermissionError("authoritative lease/fence state is unavailable")
    if isinstance(now, bool) or not isinstance(now, (int, float)):
        raise PermissionError("lease/fence verifier clock is invalid")
    expected = (
        tenant_id, project_id, device_id, capability_id, lease_id, fence_id, fence_id
    )
    actual = (
        snapshot.tenant_id, snapshot.project_id, snapshot.device_id,
        snapshot.capability_id, snapshot.lease_id, snapshot.fence_id,
        snapshot.current_fence_id,
    )
    if actual != expected:
        raise PermissionError("lease is stale or fencing generation is no longer current")
    if snapshot.revoked:
        raise PermissionError("execution lease has been revoked")
    if snapshot.lease_expires_at <= now:
        raise PermissionError("execution lease has expired")


def sign_lease_status_for_test(
    status: SignedLeaseFenceStatus,
    private_key: Ed25519PrivateKey,
) -> SignedLeaseFenceStatus:
    """Test helper only; HOARE production private keys must never enter PHyAI."""
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("private_key must be an Ed25519PrivateKey")
    signature = private_key.sign(canonical_lease_status(status))
    return SignedLeaseFenceStatus(
        authority_id=status.authority_id,
        tenant_id=status.tenant_id,
        project_id=status.project_id,
        device_id=status.device_id,
        capability_id=status.capability_id,
        lease_id=status.lease_id,
        fence_id=status.fence_id,
        current_fence_id=status.current_fence_id,
        lease_expires_at=status.lease_expires_at,
        revoked=status.revoked,
        request_nonce=status.request_nonce,
        issued_at=status.issued_at,
        response_expires_at=status.response_expires_at,
        key_id=status.key_id,
        signature=signature,
        algorithm=status.algorithm,
        contract_version=status.contract_version,
    )
