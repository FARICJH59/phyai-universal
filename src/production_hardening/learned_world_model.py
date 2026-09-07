from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence
from uuid import UUID

from .world_model import ActionCondition, PredictedFrame, WorldModelRequest, WorldModelRollout


@dataclass(frozen=True, slots=True)
class VideoFrame:
    """Opaque RGB/RGB-D frame supplied to a learned temporal model."""

    timestamp_ns: int
    payload: bytes
    encoding: str = "image/octet-stream"

    def __post_init__(self) -> None:
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not self.payload:
            raise ValueError("payload must not be empty")
        if not self.encoding.strip():
            raise ValueError("encoding is required")


@dataclass(frozen=True, slots=True)
class LearnedWorldModelRequest:
    """Temporal input contract for a learned world model.

    Frames and actions remain domain objects here. Tensor conversion is explicit
    and injected, preventing accidental claims that opaque bytes are model-ready
    tensors.
    """

    tenant_id: str
    project_id: str
    scene_id: UUID
    frames: Sequence[VideoFrame]
    actions: Sequence[ActionCondition]
    horizon: int

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.project_id.strip():
            raise ValueError("tenant_id and project_id are required")
        if not self.frames:
            raise ValueError("frames must not be empty")
        if not self.actions:
            raise ValueError("actions must not be empty")
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")


@dataclass(frozen=True, slots=True)
class TensorWorldModelInput:
    """Explicit numeric representation consumed by a learned model."""

    frame_features: Sequence[Sequence[float]]
    action_features: Sequence[Sequence[float]]
    horizon: int

    def __post_init__(self) -> None:
        if not self.frame_features:
            raise ValueError("frame_features must not be empty")
        if not self.action_features:
            raise ValueError("action_features must not be empty")
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")
        if any(not row for row in self.frame_features):
            raise ValueError("frame feature rows must not be empty")
        if any(not row for row in self.action_features):
            raise ValueError("action feature rows must not be empty")


class LearnedWorldModel(Protocol):
    model_id: str

    def predict(self, request: LearnedWorldModelRequest) -> WorldModelRollout: ...


class DiffusionWorldModel(LearnedWorldModel, Protocol):
    """Optional diffusion/video-prediction implementation boundary."""

    def sample(self, request: LearnedWorldModelRequest) -> WorldModelRollout: ...


class TensorEncoder(Protocol):
    def encode_frames(self, frames: Sequence[VideoFrame]) -> Sequence[Sequence[float]]: ...

    def encode_actions(self, actions: Sequence[ActionCondition], horizon: int) -> Sequence[Sequence[float]]: ...


class TensorLearnedModel(Protocol):
    model_id: str

    def predict(self, model_input: TensorWorldModelInput) -> Sequence[Sequence[float]]: ...


class LearnedWorldModelAdapter:
    """Existing compatibility boundary; refuses to invent learned mappings."""

    def __init__(self, model: LearnedWorldModel) -> None:
        if not getattr(model, "model_id", "").strip():
            raise ValueError("learned model must expose a model_id")
        self.model = model

    def rollout(self, request: WorldModelRequest) -> WorldModelRollout:
        raise NotImplementedError(
            "A concrete adapter must define how canonical WorldModelRequest state/action "
            "maps to the learned model's frame/action representation"
        )


class EncodedLearnedWorldModelAdapter:
    """Bridge temporal frames/actions into a learned numeric model.

    This adapter deliberately requires an encoder. It never interprets image bytes
    as floats and never invents a state representation for a learned model.
    """

    def __init__(self, model: TensorLearnedModel, encoder: TensorEncoder) -> None:
        if not getattr(model, "model_id", "").strip():
            raise ValueError("learned model must expose a model_id")
        self.model = model
        self.encoder = encoder

    def predict(self, request: LearnedWorldModelRequest) -> WorldModelRollout:
        frame_features = tuple(tuple(float(v) for v in row) for row in self.encoder.encode_frames(request.frames))
        action_features = tuple(tuple(float(v) for v in row) for row in self.encoder.encode_actions(request.actions, request.horizon))
        model_input = TensorWorldModelInput(frame_features, action_features, request.horizon)
        outputs = tuple(tuple(float(v) for v in row) for row in self.model.predict(model_input))
        if len(outputs) != request.horizon:
            raise ValueError("learned model output length must equal horizon")
        if any(not row for row in outputs):
            raise ValueError("learned model output rows must not be empty")
        frames = tuple(
            PredictedFrame(
                step=index + 1,
                state={f"state_{i}": value for i, value in enumerate(row)},
                confidence=1.0,
            )
            for index, row in enumerate(outputs)
        )
        return WorldModelRollout(
            tenant_id=request.tenant_id,
            project_id=request.project_id,
            scene_id=request.scene_id,
            frames=frames,
            model_id=self.model.model_id,
        )


class PyTorchTensorModel:
    """Concrete PyTorch bridge for action-conditioned temporal inference.

    The wrapped module must accept tensors shaped
    ``[batch, time, frame_features]`` and ``[batch, horizon, action_features]``
    and return ``[batch, horizon, state_features]``. Production callers inject
    their trained ``torch.nn.Module`` and weights.
    """

    def __init__(self, module: object, model_id: str, device: str = "cpu") -> None:
        if not model_id.strip():
            raise ValueError("model_id is required")
        self.module = module
        self.model_id = model_id
        self.device = device

    def predict(self, model_input: TensorWorldModelInput) -> Sequence[Sequence[float]]:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("PyTorch is required for PyTorchTensorModel") from exc

        frame_tensor = torch.tensor(model_input.frame_features, dtype=torch.float32, device=self.device).unsqueeze(0)
        action_tensor = torch.tensor(model_input.action_features, dtype=torch.float32, device=self.device).unsqueeze(0)
        module = self.module
        if hasattr(module, "eval"):
            module.eval()
        with torch.no_grad():
            output = module(frame_tensor, action_tensor)
        if not hasattr(output, "detach") or not hasattr(output, "cpu"):
            raise TypeError("PyTorch model must return a tensor")
        array = output.detach().cpu().numpy()
        if array.ndim != 3 or array.shape[0] != 1:
            raise ValueError("PyTorch model output must have shape [1, horizon, state_features]")
        return tuple(tuple(float(v) for v in row) for row in array[0])


def action_feature_encoder(actions: Sequence[ActionCondition], horizon: int) -> Sequence[Sequence[float]]:
    """Encode scalar action mappings into fixed-key temporal action vectors."""
    if not actions:
        raise ValueError("actions must not be empty")
    keys = tuple(sorted({key for action in actions for key in action.values}))
    if not keys:
        raise ValueError("action mappings must contain values")
    return tuple(
        tuple(float(actions[min(index, len(actions) - 1)].values.get(key, 0.0)) for key in keys)
        for index in range(horizon)
    )
