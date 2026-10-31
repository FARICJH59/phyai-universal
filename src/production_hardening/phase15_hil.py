from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable, Mapping, Protocol, Sequence
import time

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.admission_proof import AdmissionProofVerifier, SignedAdmissionProof
from src.production_hardening.lease_fencing import (
    LeaseFenceVerifier, require_current_lease_fence,
)
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedHoareClient


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


@dataclass(frozen=True, slots=True)
class HardwareObservation:
    tenant_id: str
    project_id: str
    device_id: str
    sequence: int
    timestamp_ns: int
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not all(isinstance(item, str) and item.strip() for item in (self.tenant_id, self.project_id, self.device_id)):
            raise ValueError("tenant_id, project_id, and device_id are required")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if isinstance(self.timestamp_ns, bool) or not isinstance(self.timestamp_ns, int) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative integer")
        if not self.values or any(not _finite_number(value) for value in self.values):
            raise ValueError("observation values must be non-empty and finite")


@dataclass(frozen=True, slots=True)
class ActuationRequest:
    tenant_id: str
    project_id: str
    device_id: str
    attempt_id: str
    command_digest: str
    parameters: Mapping[str, float]
    governed_command: ControlCommand
    artifact_hash: str
    policy_context: Mapping[str, str]

    def __post_init__(self) -> None:
        if not all(isinstance(item, str) and item.strip() for item in (
            self.tenant_id, self.project_id, self.device_id, self.attempt_id, self.command_digest
        )):
            raise ValueError("execution identity is required")
        if not self.parameters:
            raise ValueError("actuation parameters are required")
        if any(not isinstance(key, str) or not key.strip() or not _finite_number(value)
               for key, value in self.parameters.items()):
            raise ValueError("actuation parameter names and values must be valid and finite")
        if not isinstance(self.governed_command, ControlCommand):
            raise TypeError("actuation request requires the exact governed ControlCommand")
        if not isinstance(self.artifact_hash, str) or not self.artifact_hash.strip():
            raise ValueError("artifact_hash is required")
        if not isinstance(self.policy_context, Mapping):
            raise TypeError("policy_context must be a mapping")
        self.validate_governed_binding()

    def validate_governed_binding(self) -> None:
        command = self.governed_command
        if (self.tenant_id, self.project_id, self.attempt_id) != (
            command.tenant_id, command.project_id, str(command.attempt_id)
        ):
            raise ValueError("actuation identity does not match governed command")
        if self.device_id != command.target_id:
            raise ValueError("actuation target does not match governed command target")
        if dict(self.parameters) != dict(command.parameters):
            raise ValueError("actuation parameters do not match governed command")
        expected = GovernedHoareClient.digest_request(
            command, self.artifact_hash, self.policy_context
        )
        if self.command_digest != expected:
            raise ValueError("actuation command digest does not match governed command")


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    attempt_id: str
    device_id: str
    sequence: int
    result_digest: str
    verified: bool

    def __post_init__(self) -> None:
        if not all(isinstance(item, str) and item.strip() for item in (
            self.attempt_id, self.device_id, self.result_digest
        )):
            raise ValueError("evidence identity is required")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")


class PhysicalSensor(Protocol):
    def read(self) -> HardwareObservation: ...


class PhysicalActuator(Protocol):
    def apply(self, request: ActuationRequest) -> ExecutionEvidence: ...


class HardwareInLoopBoundary:
    """Physical I/O boundary that accepts only sealed Phase-16 authority."""

    def __init__(
        self,
        actuator: PhysicalActuator,
        admission_proof_verifier: AdmissionProofVerifier,
        lease_fence_verifier: LeaseFenceVerifier,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(admission_proof_verifier, AdmissionProofVerifier):
            raise TypeError("a trusted HOARE admission proof verifier is required")
        if not isinstance(lease_fence_verifier, LeaseFenceVerifier):
            raise TypeError("a live HOARE lease/fence verifier is required")
        self._actuator = actuator
        self._admission_proof_verifier = admission_proof_verifier
        self._lease_fence_verifier = lease_fence_verifier
        self._clock = clock

    def execute(
        self,
        request: ActuationRequest,
        authority: GovernedAdmission,
        proof: SignedAdmissionProof,
    ) -> ExecutionEvidence:
        if not isinstance(authority, GovernedAdmission):
            raise PermissionError("physical actuation requires Phase 16 governed admission")
        if not authority.accepted:
            raise PermissionError("HOARE admission denied; physical actuation blocked")
        if str(authority.attempt_id) != request.attempt_id:
            raise ValueError("governed authority attempt identity mismatch")
        # Recompute at dispatch: ControlCommand is frozen, but its parameters mapping may be mutable.
        request.validate_governed_binding()
        if authority.request_digest != request.command_digest:
            raise PermissionError("governed authority does not bind the exact actuation command")
        if not all((authority.capability_id, authority.lease_id, authority.fence_id)):
            raise PermissionError("governed authority is incomplete")
        claims = self._admission_proof_verifier.verify(
            proof,
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            device_id=request.device_id,
            attempt_id=request.attempt_id,
            request_digest=request.command_digest,
        )
        if (claims.capability_id, claims.lease_id, claims.fence_id) != (
            authority.capability_id, authority.lease_id, authority.fence_id
        ):
            raise PermissionError("signed admission proof does not match Phase 16 authority")
        lease_snapshot = self._lease_fence_verifier.validate_current(
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            device_id=request.device_id,
            capability_id=claims.capability_id,
            lease_id=claims.lease_id,
            fence_id=claims.fence_id,
        )
        require_current_lease_fence(
            lease_snapshot,
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            device_id=request.device_id,
            capability_id=claims.capability_id,
            lease_id=claims.lease_id,
            fence_id=claims.fence_id,
            now=self._clock(),
        )
        evidence = self._actuator.apply(request)
        if not isinstance(evidence, ExecutionEvidence):
            raise TypeError("actuator must return ExecutionEvidence")
        if evidence.attempt_id != request.attempt_id or evidence.device_id != request.device_id:
            raise ValueError("execution evidence identity mismatch")
        if not evidence.verified:
            raise RuntimeError("physical execution evidence failed verification")
        return evidence


def validate_sensor_sequence(observations: Sequence[HardwareObservation]) -> None:
    if not observations:
        raise ValueError("observations are required")
    first = observations[0]
    tenant = first.tenant_id
    project = first.project_id
    device = first.device_id
    previous_sequence = -1
    previous_timestamp = -1
    for observation in observations:
        if observation.tenant_id != tenant or observation.project_id != project:
            raise ValueError("cross-tenant or cross-project hardware observations")
        if observation.device_id != device:
            raise ValueError("hardware observation device identity changed")
        if observation.sequence <= previous_sequence:
            raise ValueError("hardware observation sequence must increase")
        if observation.timestamp_ns <= previous_timestamp:
            raise ValueError("hardware observation timestamp must increase")
        previous_sequence = observation.sequence
        previous_timestamp = observation.timestamp_ns
