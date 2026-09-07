from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import SpatialScene
from src.phase7_reasoning import ReasoningPipeline


def scene():
    return SpatialScene(
        tenant_id="t1", project_id="p1", scene_id=uuid4(), sequence=7,
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), reference_frame="world",
        representation=b"{}", representation_encoding="json", confidence=0.95,
        source_observation_ids=(uuid4(),), provenance_uri="urn:phyai:perception:test",
    )


def test_reasoning_produces_bounded_plan():
    result = ReasoningPipeline().reason(
        scene(), objective="maintain position", target_id="robot-1",
        command_type="velocity", safety_precondition_ids=("clear-path",),
        constraints={"velocity": 1.0},
    )
    assert result.authorization_required
    assert result.plan.target_id == "robot-1"
    assert result.plan.parameters["velocity"] == 1.0
    assert result.plan.confidence == 0.95


def test_reasoning_rejects_missing_safety_preconditions():
    with pytest.raises(ValueError, match="safety_precondition_ids"):
        ReasoningPipeline().reason(
            scene(), objective="maintain position", target_id="robot-1",
            command_type="velocity", safety_precondition_ids=(), constraints={"velocity": 1.0},
        )


def test_reasoning_preserves_scene_identity():
    s = scene()
    result = ReasoningPipeline().reason(
        s, objective="maintain position", target_id="robot-1",
        command_type="velocity", safety_precondition_ids=("clear-path",), constraints={"velocity": 1.0},
    )
    assert result.scene_id == s.scene_id
    assert result.plan.scene_id == s.scene_id


def test_reasoning_result_contains_no_execution_authority():
    result = ReasoningPipeline().reason(
        scene(), objective="maintain position", target_id="robot-1",
        command_type="velocity", safety_precondition_ids=("clear-path",), constraints={"velocity": 1.0},
    )
    assert not hasattr(result, "lease")
    assert not hasattr(result, "capability")
    assert not hasattr(result, "dispatch")
