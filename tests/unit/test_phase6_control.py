from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import SpatialScene
from src.phase6_control import ControlPipeline, SafetyValidator


def scene(confidence=0.95):
    oid = uuid4()
    return SpatialScene(
        tenant_id="t1", project_id="p1", scene_id=uuid4(), sequence=7,
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), reference_frame="world",
        representation=b"{}", representation_encoding="json", confidence=confidence,
        source_observation_ids=(oid,), provenance_uri="urn:phyai:perception:test",
    )


def test_safety_gate_allows_high_confidence_numeric_parameters():
    result = SafetyValidator().validate(scene(), {"velocity": 1.0})
    assert result.allowed


def test_safety_gate_fails_closed_on_low_confidence():
    result = SafetyValidator().validate(scene(0.89), {"velocity": 1.0})
    assert not result.allowed
    assert "scene_confidence_below_threshold" in result.reasons


def test_safety_gate_fails_closed_without_parameters():
    result = SafetyValidator().validate(scene(), {})
    assert not result.allowed


def test_control_pipeline_creates_proposal_only():
    source = scene()
    command = ControlPipeline().propose(
        source, target_id="robot-1", command_type="velocity",
        parameters={"velocity": 1.0}, safety_precondition_ids=("precondition:clear-path",),
    )
    assert command.tenant_id == source.tenant_id
    assert command.project_id == source.project_id
    assert command.scene_id == source.scene_id
    assert command.source_observation_ids == source.source_observation_ids
    assert command.is_authorization_free_proposal
    assert not hasattr(command, "lease")
    assert not hasattr(command, "capability")
    assert not hasattr(command, "authorization")
    assert not hasattr(command, "dispatch")


def test_low_confidence_proposal_is_rejected():
    with pytest.raises(ValueError, match="scene_confidence_below_threshold"):
        ControlPipeline().propose(
            scene(0.5), target_id="robot-1", command_type="velocity",
            parameters={"velocity": 1.0}, safety_precondition_ids=("precondition:clear-path",),
        )
