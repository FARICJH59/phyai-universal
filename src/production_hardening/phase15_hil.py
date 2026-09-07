from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class HardwareObservation:
    tenant_id: str
    project_id: str
    device_id: str
    sequence: int
    timestamp_ns: int
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.project_id or not self.device_id:
            raise ValueError("tenant_id, project_id, and device_id are required")
        if self.sequence < 0 or self.timestamp_ns < 0 or not self.values:
            raise ValueError("invalid hardware observation")


@dataclass(frozen=True, slots=True)
class ActuationRequest:
    tenant_id: str
    project_id: str
    device_id: str
    attempt_id: str
    command_digest: str
    parameters: Mapping[str, float]

    def __post_init__(self) -> None:
        if not all((self.tenant_id, self.project_id, self.device_id, self.attempt_id, self.command_digest)):
            raise ValueError("execution identity is required")
        if not self.parameters:
            raise ValueError("actuation parameters are required")


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    attempt_id: str
    device_id: str
    sequence: int
    result_digest: str
    verified: bool

    def __post_init__(self) -> None:
        if not self.attempt_id or not self.device_id or not self.result_digest:
            raise ValueError("evidence identity is required")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")


class PhysicalSensor(Protocol):
    def read(self) -> HardwareObservation: ...


class PhysicalActuator(Protocol):
    def apply(self, request: ActuationRequest) -> ExecutionEvidence: ...


class GovernedExecutionAuthority(Protocol):
    """Minimal authority proof supplied by the Phase 16 governance boundary."""

    accepted: bool
    attempt_id: object
    capability_id: str | None
    lease_id: str | None
    fence_id: str | None


class HardwareInLoopBoundary:
    """Physical I/O adapter that requires Phase 16-style authority before actuation."""

    def __init__(self, actuator: PhysicalActuator) -> None:
        self._actuator = actuator

    def execute(self, request: ActuationRequest, authority: GovernedExecutionAuthority) -> ExecutionEvidence:
        if not authority.accepted:
            raise PermissionError("HOARE admission denied; physical actuation blocked")
        if str(authority.attempt_id) != request.attempt_id:
            raise ValueError("governed authority attempt identity mismatch")
        if not all((authority.capability_id, authority.lease_id, authority.fence_id)):
            raise PermissionError("governed authority is incomplete")
        evidence = self._actuator.apply(request)
        if evidence.attempt_id != request.attempt_id or evidence.device_id != request.device_id:
            raise ValueError("execution evidence identity mismatch")
        if not evidence.verified:
            raise RuntimeError("physical execution evidence failed verification")
        return evidence


def validate_sensor_sequence(observations: Sequence[HardwareObservation]) -> None:
    if not observations:
        raise ValueError("observations are required")
    tenant = observations[0].tenant_id
    project = observations[0].project_id
    previous = -1
    for observation in observations:
        if observation.tenant_id != tenant or observation.project_id != project:
            raise ValueError("cross-tenant or cross-project hardware observations")
        if observation.sequence <= previous:
            raise ValueError("hardware observation sequence must increase")
        previous = observation.sequence
