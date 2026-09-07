from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping
from uuid import UUID, uuid4

from src.phase1_contracts.contracts import ControlCommand, SpatialScene
from src.phase6_control.safety.validator import SafetyValidator


class ProposalController:
    """Builds bounded ControlCommand proposals from a spatial scene."""

    def __init__(self, safety: SafetyValidator | None = None):
        self._safety = safety or SafetyValidator()

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
        result = self._safety.validate(scene, parameters)
        if not result.allowed:
            raise ValueError("control proposal rejected: " + ",".join(result.reasons))
        if not target_id.strip() or not command_type.strip():
            raise ValueError("target_id and command_type are required")
        if not safety_precondition_ids:
            raise ValueError("safety preconditions are required")
        return ControlCommand(
            tenant_id=scene.tenant_id,
            project_id=scene.project_id,
            command_id=uuid4(),
            attempt_id=attempt_id or uuid4(),
            sequence=scene.sequence,
            proposed_at=datetime.now(timezone.utc),
            target_id=target_id,
            command_type=command_type,
            parameters=dict(parameters),
            confidence=scene.confidence,
            safety_precondition_ids=safety_precondition_ids,
            scene_id=scene.scene_id,
            source_observation_ids=tuple(scene.source_observation_ids),
            provenance_uri=scene.provenance_uri,
        )
