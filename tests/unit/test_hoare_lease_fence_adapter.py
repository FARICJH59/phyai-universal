from dataclasses import replace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.production_hardening.lease_fencing import (
    HoareLeaseFenceAdapter,
    LeaseFenceLookup,
    SignedLeaseFenceStatus,
    canonical_lease_status,
    sign_lease_status_for_test,
)


_NOW = 1_800_000_000
_PRIVATE = Ed25519PrivateKey.generate()
_PUBLIC = _PRIVATE.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)


class FakeHoareTransport:
    def __init__(self, build_status):
        self.build_status = build_status
        self.requests = []

    def fetch_current(self, request):
        self.requests.append(request)
        return self.build_status(request)


def status_for(request, **overrides):
    values = dict(
        authority_id="hoare-control-plane",
        tenant_id=request.tenant_id,
        project_id=request.project_id,
        device_id=request.device_id,
        capability_id=request.capability_id,
        lease_id=request.lease_id,
        fence_id=request.fence_id,
        current_fence_id=request.fence_id,
        lease_expires_at=_NOW + 120,
        revoked=False,
        request_nonce=request.nonce,
        issued_at=_NOW,
        response_expires_at=_NOW + 5,
        key_id="hoare-key-1",
        signature=b"0" * 64,
    )
    values.update(overrides)
    unsigned = SignedLeaseFenceStatus(**values)
    return sign_lease_status_for_test(unsigned, _PRIVATE)


def adapter(transport, *, nonce="n" * 64, **kwargs):
    return HoareLeaseFenceAdapter(
        transport,
        {"hoare-key-1": _PUBLIC},
        clock=lambda: _NOW,
        nonce_factory=lambda: nonce,
        **kwargs,
    )


def validate(instance):
    return instance.validate_current(
        tenant_id="tenant-a",
        project_id="project-a",
        device_id="edge-01",
        capability_id="cap-01",
        lease_id="lease-01",
        fence_id="fence-7",
    )


def test_adapter_returns_only_verified_signed_current_lease_status():
    transport = FakeHoareTransport(lambda req: status_for(req))
    snapshot = validate(adapter(transport))
    assert snapshot.current_fence_id == "fence-7"
    assert snapshot.revoked is False
    assert transport.requests[0].contract_version == "hoare.lease-fence.v1"
    assert len(transport.requests[0].nonce) >= 32


def test_adapter_rejects_replayed_or_wrong_nonce_response():
    transport = FakeHoareTransport(lambda req: status_for(req, request_nonce="x" * 64))
    with pytest.raises(PermissionError, match="nonce mismatch"):
        validate(adapter(transport))


def test_adapter_rejects_invalid_signature():
    def tampered(req):
        signed = status_for(req)
        return replace(signed, current_fence_id="fence-attacker")
    with pytest.raises(PermissionError, match="signature is invalid"):
        validate(adapter(FakeHoareTransport(tampered)))


def test_adapter_rejects_untrusted_signing_key():
    def unknown_key(req):
        return status_for(req, key_id="unknown-key")
    with pytest.raises(PermissionError, match="key is not trusted"):
        validate(adapter(FakeHoareTransport(unknown_key)))


def test_adapter_rejects_stale_signed_status():
    transport = FakeHoareTransport(lambda req: status_for(req, issued_at=_NOW - 30))
    with pytest.raises(PermissionError, match="status is stale"):
        validate(adapter(transport, max_response_age_seconds=5))


def test_adapter_rejects_response_expired_before_dispatch():
    transport = FakeHoareTransport(
        lambda req: status_for(req, issued_at=_NOW - 10, response_expires_at=_NOW - 5)
    )
    with pytest.raises(PermissionError, match="response has expired"):
        validate(adapter(transport, max_response_age_seconds=30))


def test_adapter_rejects_overlong_status_lifetime():
    transport = FakeHoareTransport(
        lambda req: status_for(req, response_expires_at=_NOW + 30)
    )
    with pytest.raises(PermissionError, match="lifetime exceeds"):
        validate(adapter(transport, max_response_lifetime_seconds=10))


def test_adapter_rejects_identity_substitution():
    transport = FakeHoareTransport(lambda req: status_for(req, device_id="other-device"))
    with pytest.raises(PermissionError, match="different authority"):
        validate(adapter(transport))


def test_adapter_rejects_unsupported_contract_version():
    transport = FakeHoareTransport(
        lambda req: status_for(req, contract_version="hoare.lease-fence.v2")
    )
    with pytest.raises(PermissionError, match="contract version"):
        validate(adapter(transport))


def test_adapter_rejects_non_signed_transport_response():
    transport = FakeHoareTransport(lambda req: {"revoked": False})
    with pytest.raises(PermissionError, match="invalid status contract"):
        validate(adapter(transport))


def test_lookup_rejects_short_nonce():
    with pytest.raises(ValueError, match="nonce"):
        LeaseFenceLookup(
            tenant_id="t", project_id="p", device_id="d", capability_id="c",
            lease_id="l", fence_id="f", nonce="short", requested_at=_NOW,
        )


def test_canonical_status_is_deterministic():
    transport = FakeHoareTransport(lambda req: status_for(req))
    signed = transport.fetch_current(
        LeaseFenceLookup(
            tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
            capability_id="cap-01", lease_id="lease-01", fence_id="fence-7",
            nonce="n" * 64, requested_at=_NOW,
        )
    )
    assert canonical_lease_status(signed) == canonical_lease_status(signed)


@pytest.mark.parametrize("bad_clock", [float("nan"), float("inf"), float("-inf"), True])
def test_adapter_rejects_non_finite_or_boolean_clock(bad_clock):
    transport = FakeHoareTransport(lambda req: status_for(req))
    instance = HoareLeaseFenceAdapter(
        transport, {"hoare-key-1": _PUBLIC}, clock=lambda: bad_clock,
        nonce_factory=lambda: "n" * 64,
    )
    with pytest.raises(PermissionError, match="clock is invalid"):
        validate(instance)
