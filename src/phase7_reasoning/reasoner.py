from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.phase1_contracts.contracts import ControlCommand, SpatialScene
from src.phase7_reasoning.agents.reasoning_agent import PlannerReasoningAgent
from src.phase7_reasoning.planners.planner import DeterministicPlanner, ReasoningRequest


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    plan_id: UUID
    scene_id: UUID
    plan: object
    generated_at: datetime
    authorization_required: bool = True


class ReasoningPipeline:
    """Turns scene knowledge into a control proposal; it cannot authorize execution."""

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

    @staticmethod
    def to_control_command(result: ReasoningResult) -> ControlCommand:
        """Materialize a proposal only; HOARE remains the authority boundary."""
        plan = result.plan
        return ControlCommand(
            tenant_id="", project_id="", command_id=uuid4(), attempt_id=uuid4(),
            sequence=0, proposed_at=datetime.now(timezone.utc), target_id=plan.target_id,
            command_type=plan.command_type, parameters=plan.parameters,
            confidence=plan.confidence, safety_precondition_ids=(),
            scene_id=plan.scene_id, source_observation_ids=(), provenance_uri="urn:phyai:reasoning",
        )
