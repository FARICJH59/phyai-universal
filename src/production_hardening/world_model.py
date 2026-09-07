from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ActionCondition:
    """A proposed action vector used only as conditioning input."""

    command_type: str
    values: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.command_type.strip():
            raise ValueError("command_type is required")
        if not self.values:
            raise ValueError("action values must not be empty")
        if any(not k.strip() for k in self.values):
            raise ValueError("action names must be non-empty")
        if any(not isinstance(v, (int, float)) for v in self.values.values()):
            raise ValueError("action values must be numeric")


@dataclass(frozen=True, slots=True)
class WorldModelRequest:
    tenant_id: str
    project_id: str
    scene_id: UUID
    state: Mapping[str, float]
    action: ActionCondition
    horizon: int

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.project_id.strip():
            raise ValueError("tenant_id and project_id are required")
        if not self.state:
            raise ValueError("state must not be empty")
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")


@dataclass(frozen=True, slots=True)
class PredictedFrame:
    step: int
    state: Mapping[str, float]
    confidence: float


@dataclass(frozen=True, slots=True)
class WorldModelRollout:
    tenant_id: str
    project_id: str
    scene_id: UUID
    frames: Sequence[PredictedFrame]
    model_id: str


class WorldModel(Protocol):
    def rollout(self, request: WorldModelRequest) -> WorldModelRollout: ...


class ActionConditionedReferenceWorldModel:
    """Deterministic action-conditioned rollout for contract and benchmark use.

    This is deliberately not presented as a learned diffusion or transformer model.
    A learned backend can implement the same WorldModel protocol without changing
    the surrounding contracts.
    """

    model_id = "action-conditioned-reference-v1"

    def rollout(self, request: WorldModelRequest) -> WorldModelRollout:
        state = dict(request.state)
        frames: list[PredictedFrame] = []
        acceleration = float(request.action.values.get("acceleration", 0.0))
        for step in range(1, request.horizon + 1):
            state["velocity"] = state.get("velocity", 0.0) + acceleration
            state["position"] = state.get("position", 0.0) + state["velocity"]
            frames.append(PredictedFrame(step, dict(state), confidence=1.0))
        return WorldModelRollout(
            request.tenant_id,
            request.project_id,
            request.scene_id,
            tuple(frames),
            self.model_id,
        )
