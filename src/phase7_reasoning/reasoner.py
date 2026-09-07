from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.phase1_contracts.contracts import SpatialScene
from src.phase7_reasoning.agents.reasoning_agent import PlannerReasoningAgent
from src.phase7_reasoning.planners.planner import DeterministicPlanner, ReasoningRequest, Plan


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    plan_id: UUID
    scene_id: UUID
    plan: Plan
    generated_at: datetime
    authorization_required: bool = True


class ReasoningPipeline:
    """Turns scene knowledge into a bounded plan; it cannot authorize execution."""

    def __init__(self, agent=None):
        self._agent = agent or PlannerReasoningAgent(DeterministicPlanner())

    def reason(self, scene: SpatialScene, *, objective: str, target_id: str,
               command_type: str, safety_precondition_ids: tuple[str, ...],
               constraints: dict[str, float]) -> ReasoningResult:
        request = ReasoningRequest(scene, objective, target_id, command_type,
                                   safety_precondition_ids, constraints)
        plan = self._agent.reason(request)
        return ReasoningResult(uuid4(), scene.scene_id, plan,
                               datetime.now(timezone.utc), True)
