from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence
from uuid import UUID

from .world_model import ActionCondition, PredictedFrame, WorldModelRequest, WorldModelRollout


@dataclass(frozen=True, slots=True)
class VideoFrame:
    """Opaque RGB/RGB-D frame supplied to a learned world model."""

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


class LearnedWorldModel(Protocol):
    model_id: str

    def predict(self, request: LearnedWorldModelRequest) -> WorldModelRollout: ...


class DiffusionWorldModel(LearnedWorldModel, Protocol):
    """Optional diffusion/video-prediction implementation boundary.

    The protocol intentionally carries no authorization or actuation capability.
    A concrete implementation must be supplied by a real trained model runtime.
    """

    def sample(self, request: LearnedWorldModelRequest) -> WorldModelRollout: ...


class LearnedWorldModelAdapter:
    """Adapt a learned video/action model to the existing WorldModel interface."""

    def __init__(self, model: LearnedWorldModel) -> None:
        if not getattr(model, "model_id", "").strip():
            raise ValueError("learned model must expose a model_id")
        self.model = model

    def rollout(self, request: WorldModelRequest) -> WorldModelRollout:
        raise NotImplementedError(
            "A concrete adapter must define how canonical WorldModelRequest state/action "
            "maps to the learned model's frame/action representation"
        )
