from __future__ import annotations

from typing import Mapping
from uuid import UUID

from src.phase1_contracts.contracts import ControlCommand, SpatialScene
from src.phase6_control.controllers.proposal_controller import ProposalController


class ControlPipeline:
    """Phase 6 control boundary: scene -> validated proposal, never dispatch."""

    def __init__(self, controller: ProposalController | None = None):
        self._controller = controller or ProposalController()

    def propose(
        self,
        scene: SpatialScene,
        *,
        target_id: str,
        command_type: str,
        parameters: Mapping[str, float],
        safety_precondition_ids: tuple[str, ...],
        attempt_id: UUID | None = None,
    ) -> ControlCommand:
        return self._controller.propose(
            scene,
            target_id=target_id,
            command_type=command_type,
            parameters=parameters,
            safety_precondition_ids=safety_precondition_ids,
            attempt_id=attempt_id,
        )
