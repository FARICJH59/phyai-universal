from uuid import uuid4

import pytest

from src.production_hardening.learned_world_model import (
    EncodedLearnedWorldModelAdapter,
    LearnedWorldModelRequest,
    TensorWorldModelInput,
    VideoFrame,
    action_feature_encoder,
)
from src.production_hardening.world_model import ActionCondition


def request(horizon=3):
    return LearnedWorldModelRequest(
        tenant_id="tenant-a",
        project_id="project-a",
        scene_id=uuid4(),
        frames=[VideoFrame(1, b"rgb"), VideoFrame(2, b"rgb")],
        actions=[ActionCondition("move", {"x": 1.0})],
        horizon=horizon,
    )


def test_action_feature_encoder_is_fixed_key_and_temporal():
    actions = [
        ActionCondition("move", {"z": 2.0, "x": 1.0}),
        ActionCondition("move", {"x": 3.0, "z": 4.0}),
    ]
    assert action_feature_encoder(actions, 3) == ((1.0, 2.0), (3.0, 4.0), (3.0, 4.0))


def test_encoded_adapter_preserves_identity_and_horizon():
    class Encoder:
        def encode_frames(self, frames):
            return ((0.1, 0.2),) * len(frames)

        def encode_actions(self, actions, horizon):
            return ((1.0, 0.0),) * horizon

    class Model:
        model_id = "toy-learned-v1"

        def predict(self, model_input: TensorWorldModelInput):
            assert len(model_input.frame_features) == 2
            assert len(model_input.action_features) == 3
            assert model_input.horizon == 3
            return ((0.1, 0.2), (0.2, 0.3), (0.3, 0.4))

    req = request()
    rollout = EncodedLearnedWorldModelAdapter(Model(), Encoder()).predict(req)
    assert rollout.tenant_id == req.tenant_id
    assert rollout.project_id == req.project_id
    assert rollout.scene_id == req.scene_id
    assert [frame.step for frame in rollout.frames] == [1, 2, 3]
    assert rollout.model_id == "toy-learned-v1"


def test_encoded_adapter_rejects_wrong_horizon():
    class Encoder:
        def encode_frames(self, frames):
            return ((0.0,),)

        def encode_actions(self, actions, horizon):
            return ((1.0,),) * horizon

    class Model:
        model_id = "toy"

        def predict(self, model_input):
            return ((0.0,),)

    with pytest.raises(ValueError, match="output length"):
        EncodedLearnedWorldModelAdapter(Model(), Encoder()).predict(request(horizon=2))


def test_encoded_adapter_requires_model_identity():
    class Model:
        model_id = ""

    class Encoder:
        pass

    with pytest.raises(ValueError, match="model_id"):
        EncodedLearnedWorldModelAdapter(Model(), Encoder())
