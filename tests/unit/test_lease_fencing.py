import pytest

from src.production_hardening.lease_fencing import (
    LeaseFenceSnapshot,
    require_current_lease_fence,
)


def snapshot(**overrides):
    values = dict(
        tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
        capability_id="cap-01", lease_id="lease-01", fence_id="fence-7",
        current_fence_id="fence-7", lease_expires_at=1_900_000_000, revoked=False,
    )
    values.update(overrides)
    return LeaseFenceSnapshot(**values)


def validate(value):
    require_current_lease_fence(
        value, tenant_id="tenant-a", project_id="project-a", device_id="edge-01",
        capability_id="cap-01", lease_id="lease-01", fence_id="fence-7",
        now=1_800_000_000,
    )


def test_accepts_current_unrevoked_unexpired_lease_and_fence():
    validate(snapshot())


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "tenant-b"),
    ("project_id", "project-b"),
    ("device_id", "edge-02"),
    ("capability_id", "cap-other"),
    ("lease_id", "lease-other"),
    ("fence_id", "fence-6"),
    ("current_fence_id", "fence-8"),
])
def test_rejects_identity_or_fencing_generation_mismatch(field, value):
    with pytest.raises(PermissionError, match="stale or fencing"):
        validate(snapshot(**{field: value}))


def test_rejects_revoked_lease():
    with pytest.raises(PermissionError, match="revoked"):
        validate(snapshot(revoked=True))


def test_rejects_expired_lease():
    with pytest.raises(PermissionError, match="expired"):
        validate(snapshot(lease_expires_at=1_799_999_999))


@pytest.mark.parametrize("value", [True, -1, 1.5, "1900000000"])
def test_snapshot_rejects_invalid_lease_expiry(value):
    with pytest.raises(ValueError, match="lease_expires_at"):
        snapshot(lease_expires_at=value)


def test_snapshot_rejects_non_boolean_revocation_flag():
    with pytest.raises(ValueError, match="revoked"):
        snapshot(revoked=1)
