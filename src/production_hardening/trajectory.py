from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Protocol

from .world_model import ActionCondition, WorldModel, WorldModelRequest


@dataclass(frozen=True, slots=True)
class Trajectory:
    states: Sequence[Mapping[str, float]]
    model_id: str


class TrajectoryGenerator(Protocol):
    def generate(self, request: WorldModelRequest) -> Trajectory: ...


class AutoregressiveTrajectoryGenerator:
    """Rolls a world model forward one step at a time.

    The generator is intentionally model-agnostic: learned autoregressive models,
    simulators, or compiled inference engines can be substituted behind WorldModel.
    """

    def __init__(self, world_model: WorldModel) -> None:
        self.world_model = world_model

    def generate(self, request: WorldModelRequest) -> Trajectory:
        rollout = self.world_model.rollout(request)
        return Trajectory(
            states=tuple(frame.state for frame in rollout.frames),
            model_id=rollout.model_id,
        )


def action_vector_from_mapping(command_type: str, parameters: Mapping[str, float]) -> ActionCondition:
    return ActionCondition(command_type=command_type, values=dict(parameters))
