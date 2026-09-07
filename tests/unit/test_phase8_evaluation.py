from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand, SpatialScene
from src.phase8_evaluation.evaluator import DeterministicEvaluator
from src.phase8_evaluation.critics.critic import DeterministicCritic


def scene():
    return SpatialScene("t1", "p1", uuid4(), 1, datetime(2026, 1, 1, tzinfo=timezone.utc), "world", b"{}", "json", 0.95, (uuid4(),), "urn:test")


def command(s):
    return ControlCommand("t1", "p1", uuid4(), uuid4(), 1, datetime(2026, 1, 1, tzinfo=timezone.utc), "robot-1", "velocity", {"velocity": 1.0}, 0.95, ("clear-path",), s.scene_id, s.source_observation_ids, "urn:test")


def test_evaluator_accepts_matching_proposal():
    s = scene()
    result = DeterministicEvaluator().evaluate(s, command(s), {"velocity": 1.0})
    assert result.passed
    assert result.score == 1.0


def test_evaluator_rejects_missing_parameter():
    s = scene()
    result = DeterministicEvaluator().evaluate(s, command(s), {"velocity": 2.0, "yaw": 0.1})
    assert not result.passed
    assert any("missing_expected_parameter:yaw" == x for x in result.failure_modes)


def test_evaluator_rejects_cross_tenant():
    s = scene()
    c = command(s)
    c = ControlCommand("t2", c.project_id, c.command_id, c.attempt_id, c.sequence, c.proposed_at, c.target_id, c.command_type, c.parameters, c.confidence, c.safety_precondition_ids, c.scene_id, c.source_observation_ids, c.provenance_uri)
    with pytest.raises(ValueError, match="cross-tenant"):
        DeterministicEvaluator().evaluate(s, c, {"velocity": 1.0})


def test_critic_is_bounded():
    result = DeterministicCritic().critique({"max_absolute_error": 0.01})
    assert result.passed
    assert result.score == 0.99
