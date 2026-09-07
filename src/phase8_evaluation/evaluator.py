from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
from uuid import UUID, uuid5

from src.phase1_contracts.contracts import ControlCommand, SpatialScene


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: UUID
    tenant_id: str
    project_id: str
    scene_id: UUID
    expected: Mapping[str, float]
    actual: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    case_id: UUID
    passed: bool
    score: float
    metrics: Mapping[str, float]
    failure_modes: tuple[str, ...]


class DeterministicEvaluator:
    """Reference evaluator for bounded control proposals."""

    NAMESPACE = UUID("7b3d0c2a-2b76-4a61-8e0f-1bcb8f6e4c01")

    def evaluate(self, scene: SpatialScene, command: ControlCommand,
                 expected: Mapping[str, float]) -> EvaluationResult:
        if scene.tenant_id != command.tenant_id or scene.project_id != command.project_id:
            raise ValueError("cross-tenant or cross-project evaluation is forbidden")
        if scene.scene_id != command.scene_id:
            raise ValueError("command scene identity does not match evaluation scene")
        if not expected:
            raise ValueError("expected values must not be empty")
        actual = {k: float(v) for k, v in command.parameters.items() if isinstance(v, (int, float))}
        errors = [abs(float(expected[k]) - actual[k]) for k in expected if k in actual]
        missing = [k for k in expected if k not in actual]
        failures = tuple(["missing_expected_parameter:" + k for k in missing] + (["parameter_error_above_tolerance"] if errors and max(errors) > 0.05 else []))
        score = 0.0 if missing else max(0.0, 1.0 - (max(errors) if errors else 0.0))
        case_id = uuid5(self.NAMESPACE, f"{scene.tenant_id}|{scene.project_id}|{scene.scene_id}|{command.command_id}")
        return EvaluationResult(case_id, not failures, score, {"max_absolute_error": max(errors) if errors else 0.0}, failures)
