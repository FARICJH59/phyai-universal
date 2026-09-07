import pytest

from src.production_hardening.phase15_hil import (
    ActuationRequest,
    ExecutionEvidence,
    HardwareInLoopBoundary,
    HardwareObservation,
    validate_sensor_sequence,
)


class Authority:
    def __init__(self, accepted=True, attempt_id="attempt-1", complete=True):
        self.accepted = accepted
        self.attempt_id = attempt_id
        self.capability_id = "cap-1" if complete else None
        self.lease_id = "lease-1" if complete else None
        self.fence_id = "fence-1" if complete else None


class Actuator:
    def __init__(self, verified=True):
        self.verified = verified
        self.calls = 0

    def apply(self, request):
        self.calls += 1
        return ExecutionEvidence(request.attempt_id, request.device_id, 1, "digest", self.verified)


def request():
    return ActuationRequest("tenant", "project", "robot-1", "attempt-1", "command-digest", {"velocity": 1.0})


def test_hil_requires_governed_admission():
    actuator = Actuator()
    with pytest.raises(PermissionError, match="admission denied"):
        HardwareInLoopBoundary(actuator).execute(request(), Authority(False))
    assert actuator.calls == 0


def test_hil_requires_complete_governed_authority():
    actuator = Actuator()
    with pytest.raises(PermissionError, match="authority is incomplete"):
        HardwareInLoopBoundary(actuator).execute(request(), Authority(True, complete=False))
    assert actuator.calls == 0


def test_hil_binds_attempt_to_governed_authority():
    actuator = Actuator()
    with pytest.raises(ValueError, match="attempt identity"):
        HardwareInLoopBoundary(actuator).execute(request(), Authority(True, attempt_id="other-attempt"))
    assert actuator.calls == 0


def test_hil_accepts_verified_execution_after_governed_admission():
    actuator = Actuator()
    evidence = HardwareInLoopBoundary(actuator).execute(request(), Authority(True))
    assert evidence.verified
    assert evidence.attempt_id == "attempt-1"
    assert actuator.calls == 1


def test_hil_rejects_unverified_evidence():
    with pytest.raises(RuntimeError, match="evidence failed verification"):
        HardwareInLoopBoundary(Actuator(False)).execute(request(), Authority(True))


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
