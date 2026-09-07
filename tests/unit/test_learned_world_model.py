from uuid import uuid4

from src.production_hardening.learned_world_model import (
    LearnedWorldModelAdapter,
    LearnedWorldModelRequest,
    VideoFrame,
)
from src.production_hardening.world_model import ActionCondition, WorldModelRequest


def test_learned_request_requires_real_observation_and_action_data():
    request = LearnedWorldModelRequest(
        tenant_id="tenant-a",
        project_id="project-a",
        scene_id=uuid4(),
        frames=[VideoFrame(1, b"rgb")],
        actions=[ActionCondition("move", {"x": 1.0})],
        horizon=2,
    )
    assert request.horizon == 2


def test_learned_adapter_does_not_fabricate_mapping():
    class Model:
        model_id = "trained-model"

    adapter = LearnedWorldModelAdapter(Model())
    request = WorldModelRequest(
        tenant_id="tenant-a",
        project_id="project-a",
        scene_id=uuid4(),
        state={"position": 0.0},
        action=ActionCondition("move", {"x": 1.0}),
        horizon=1,
    )
    try:
        adapter.rollout(request)
    except NotImplementedError as exc:
        assert "canonical WorldModelRequest" in str(exc)
    else:
        raise AssertionError("Learned adapters must not silently invent a model mapping")
