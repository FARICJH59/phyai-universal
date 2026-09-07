import pytest

from src.production_hardening.phase15_hil import (
    ActuationRequest,
    ExecutionEvidence,
    HardwareInLoopBoundary,
    HardwareObservation,
    validate_sensor_sequence,
)


class Admission:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def admit(self, request):
        return self.allowed


class Actuator:
    def __init__(self, verified=True):
        self.verified = verified

    def apply(self, request):
        return ExecutionEvidence(request.attempt_id, request.device_id, 1, "digest", self.verified)


def request():
    return ActuationRequest("tenant", "project", "robot-1", "attempt-1", "command-digest", {"velocity": 1.0})


def test_hil_requires_hoare_admission():
    with pytest.raises(PermissionError, match="admission denied"):
        HardwareInLoopBoundary(Admission(False), Actuator()).execute(request())


def test_hil_accepts_verified_execution_after_admission():
    evidence = HardwareInLoopBoundary(Admission(True), Actuator()).execute(request())
    assert evidence.verified
    assert evidence.attempt_id == "attempt-1"


def test_hil_rejects_unverified_evidence():
    with pytest.raises(RuntimeError, match="evidence failed verification"):
        HardwareInLoopBoundary(Admission(True), Actuator(False)).execute(request())


def test_sensor_sequence_preserves_tenant_project_and_order():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (1.0,)),
        HardwareObservation("tenant", "project", "robot-1", 1, 20, (2.0,)),
    ]
    validate_sensor_sequence(observations)


def test_sensor_sequence_rejects_cross_tenant():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (1.0,)),
        HardwareObservation("other", "project", "robot-1", 1, 20, (2.0,)),
    ]
    with pytest.raises(ValueError, match="cross-tenant"):
        validate_sensor_sequence(observations)


def test_sensor_sequence_rejects_replay_or_reordering():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 1, 10, (1.0,)),
        HardwareObservation("tenant", "project", "robot-1", 1, 20, (2.0,)),
    ]
    with pytest.raises(ValueError, match="sequence must increase"):
        validate_sensor_sequence(observations)
