from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase15_hil import (
    ActuationRequest,
    ExecutionEvidence,
    HardwareInLoopBoundary,
    HardwareObservation,
    validate_sensor_sequence,
)
from src.production_hardening.phase16_hoare_integration import GovernedHoareClient, TransportAdmission


class FakeTransport:
    def __init__(self, admission):
        self.admission = admission

    def admit(self, request):
        return self.admission


def command():
    return ControlCommand(
        tenant_id="tenant", project_id="project", command_id=uuid4(), attempt_id=uuid4(),
        sequence=1, proposed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        target_id="robot-1", command_type="position", parameters={"velocity": 1.0}, confidence=0.95,
        safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )


def context():
    return {"tenant_id": "tenant", "project_id": "project", "policy_digest": "policy-1"}


def governed_authority(cmd):
    digest = GovernedHoareClient.digest_request(cmd, "artifact", context())
    response = TransportAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted", digest)
    return GovernedHoareClient(FakeTransport(response)).admit(cmd, "artifact", context())


class Actuator:
    def __init__(self, verified=True):
        self.verified = verified
        self.calls = 0

    def apply(self, request):
        self.calls += 1
        return ExecutionEvidence(request.attempt_id, request.device_id, 1, "digest", self.verified)


def request(cmd):
    return ActuationRequest(cmd.tenant_id, cmd.project_id, "robot-1", str(cmd.attempt_id), "command-digest", {"velocity": 1.0})


def test_hil_rejects_fabricated_structural_authority():
    actuator = Actuator()
    fabricated = type("Authority", (), {
        "accepted": True, "attempt_id": "attempt", "capability_id": "cap-1",
        "lease_id": "lease-1", "fence_id": "fence-1",
    })()
    cmd = command()
    req = request(cmd)
    with pytest.raises(PermissionError, match="requires Phase 16"):
        HardwareInLoopBoundary(actuator).execute(req, fabricated)
    assert actuator.calls == 0


def test_hil_accepts_only_phase16_governed_admission():
    cmd = command()
    actuator = Actuator()
    evidence = HardwareInLoopBoundary(actuator).execute(request(cmd), governed_authority(cmd))
    assert evidence.verified
    assert evidence.attempt_id == str(cmd.attempt_id)
    assert actuator.calls == 1


def test_hil_rejects_denied_phase16_admission():
    cmd = command()
    denied = TransportAdmission(False, cmd.attempt_id, None, None, None, "denied")
    authority = GovernedHoareClient(FakeTransport(denied)).admit(cmd, "artifact", context())
    actuator = Actuator()
    with pytest.raises(PermissionError, match="admission denied"):
        HardwareInLoopBoundary(actuator).execute(request(cmd), authority)
    assert actuator.calls == 0


def test_hil_binds_attempt_to_governed_authority():
    cmd = command()
    actuator = Actuator()
    req = ActuationRequest(cmd.tenant_id, cmd.project_id, "robot-1", str(uuid4()), "command-digest", {"velocity": 1.0})
    with pytest.raises(ValueError, match="attempt identity"):
        HardwareInLoopBoundary(actuator).execute(req, governed_authority(cmd))
    assert actuator.calls == 0


def test_hil_rejects_unverified_evidence():
    cmd = command()
    with pytest.raises(RuntimeError, match="evidence failed verification"):
        HardwareInLoopBoundary(Actuator(False)).execute(request(cmd), governed_authority(cmd))


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
