from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from uuid import UUID

from src.phase1_contracts.contracts import SpatialScene


@dataclass(frozen=True, slots=True)
class ReasoningRequest:
    scene: SpatialScene
    objective: str
    target_id: str
    command_type: str
    safety_precondition_ids: tuple[str, ...]
    constraints: Mapping[str, float]

    def __post_init__(self):
        if not self.objective.strip() or not self.target_id.strip() or not self.command_type.strip():
            raise ValueError("objective, target_id, and command_type are required")
        if not self.safety_precondition_ids:
            raise ValueError("safety_precondition_ids must not be empty")
        if any(not k.strip() for k in self.constraints):
            raise ValueError("constraint names must be non-empty")


@dataclass(frozen=True, slots=True)
class Plan:
    scene_id: UUID
    target_id: str
    command_type: str
    parameters: Mapping[str, float]
    confidence: float
    planner_id: str
    rationale: str


class Planner(Protocol):
    def plan(self, request: ReasoningRequest) -> Plan: ...


class DeterministicPlanner:
    """Reference planner that emits a bounded proposal, never an executable action."""

    planner_id = "deterministic-planner-v1"

    def plan(self, request: ReasoningRequest) -> Plan:
        values = dict(request.constraints)
        confidence = min(request.scene.confidence, 1.0)
        return Plan(
            scene_id=request.scene.scene_id,
            target_id=request.target_id,
            command_type=request.command_type,
            parameters=values,
            confidence=confidence,
            planner_id=self.planner_id,
            rationale=f"reference plan for objective: {request.objective.strip()}",
        )
