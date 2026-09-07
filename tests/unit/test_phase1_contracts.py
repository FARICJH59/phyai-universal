from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts.contracts import (
    ContractIdentity,
    ContractValidationError,
    ControlCommand,
    SensorObservation,
    SpatialScene,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def identity():
    return ContractIdentity("tenant-a", "project-a", "camera-1", 1, NOW)


def test_sensor_observation_requires_provenance_and_bytes():
    observation = SensorObservation(identity(), uuid4(), "camera", "base", b"frame", "raw", 0.95, "cal-1", "evidence://1")
    assert observation.identity.tenant_id == "tenant-a"


def test_sensor_observation_rejects_invalid_confidence():
    with pytest.raises(ContractValidationError):
        SensorObservation(identity(), uuid4(), "camera", "base", b"frame", "raw", 1.1, "cal-1", "evidence://1")


def test_scene_requires_source_observation():
    with pytest.raises(ContractValidationError):
        SpatialScene("tenant-a", "project-a", uuid4(), 1, NOW, "map", b"scene", "json", 0.9)


def test_control_command_is_only_a_proposal():
    command = ControlCommand(
        "tenant-a", "project-a", uuid4(), uuid4(), 1, NOW, "arm-1", "joint_delta",
        {"joint": 1, "delta": 0.1}, 0.91, ["workspace-clear"], uuid4(), [uuid4()], "evidence://scene/1"
    )
    assert command.is_authorization_free_proposal is True
    assert not hasattr(command, "authorization_token")


def test_contracts_reject_naive_timestamps():
    with pytest.raises(ContractValidationError):
        ContractIdentity("tenant-a", "project-a", "camera-1", 1, datetime(2026, 1, 1))
