from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LeaseFenceSnapshot:
    """Fresh authoritative lease/fence state returned by the HOARE control plane."""

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
    """Adapter contract for a live, authoritative HOARE lease/fence lookup."""

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
