from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.phase1_contracts.contracts import SpatialScene


@dataclass(frozen=True, slots=True)
class SafetyValidationResult:
    allowed: bool
    reasons: tuple[str, ...] = ()


class SafetyValidator:
    """Deterministic pre-command safety gate; it grants no execution authority."""

    def validate(self, scene: SpatialScene, parameters: Mapping[str, float], *, minimum_confidence: float = 0.90) -> SafetyValidationResult:
        reasons: list[str] = []
        if scene.confidence < minimum_confidence:
            reasons.append("scene_confidence_below_threshold")
        if not parameters:
            reasons.append("control_parameters_required")
        for name, value in parameters.items():
            if not isinstance(value, (int, float)):
                reasons.append(f"non_numeric_parameter:{name}")
        return SafetyValidationResult(not reasons, tuple(reasons))
