from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RobustnessThreshold:
    max_output_relative_change: float = 0.20
    max_trajectory_error: float = 0.25
    min_confidence: float = 0.80

    def __post_init__(self) -> None:
        if self.max_output_relative_change < 0 or self.max_trajectory_error < 0:
            raise ValueError("robustness thresholds must be non-negative")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class RobustnessEvaluation:
    modality: str
    output_relative_change: float
    trajectory_error: float
    confidence: float
    passed: bool
    reason: str


class SimToRealRobustnessHarness:
    """Evaluates perturbation sensitivity and fails closed below safety confidence."""

    def __init__(self, threshold: RobustnessThreshold | None = None) -> None:
        self.threshold = threshold or RobustnessThreshold()

    def evaluate(
        self,
        modality: str,
        baseline_output: Sequence[float],
        perturbed_output: Sequence[float],
        baseline_trajectory: Sequence[Sequence[float]],
        perturbed_trajectory: Sequence[Sequence[float]],
        confidence: float,
    ) -> RobustnessEvaluation:
        if not modality.strip():
            raise ValueError("modality is required")
        if not baseline_output or len(baseline_output) != len(perturbed_output):
            raise ValueError("outputs must be non-empty and equal length")
        if not baseline_trajectory or len(baseline_trajectory) != len(perturbed_trajectory):
            raise ValueError("trajectories must be non-empty and equal length")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        base_norm = sum(float(x) ** 2 for x in baseline_output) ** 0.5
        diff_norm = sum((float(a) - float(b)) ** 2 for a, b in zip(baseline_output, perturbed_output)) ** 0.5
        relative_change = diff_norm / max(base_norm, 1e-12)

        errors: list[float] = []
        for base, perturbed in zip(baseline_trajectory, perturbed_trajectory):
            if len(base) != len(perturbed) or not base:
                raise ValueError("trajectory state shapes must match and be non-empty")
            errors.append(sum((float(a) - float(b)) ** 2 for a, b in zip(base, perturbed)) ** 0.5)
        trajectory_error = sum(errors) / len(errors)

        if confidence < self.threshold.min_confidence:
            return RobustnessEvaluation(modality, relative_change, trajectory_error, confidence, False, "confidence_below_safety_threshold")
        if relative_change > self.threshold.max_output_relative_change:
            return RobustnessEvaluation(modality, relative_change, trajectory_error, confidence, False, "output_sensitivity_exceeded")
        if trajectory_error > self.threshold.max_trajectory_error:
            return RobustnessEvaluation(modality, relative_change, trajectory_error, confidence, False, "trajectory_deviation_exceeded")
        return RobustnessEvaluation(modality, relative_change, trajectory_error, confidence, True, "within_robustness_thresholds")


def perturb_modalities(
    modalities: Mapping[str, Sequence[float]],
    modality: str,
    perturbation: Callable[[Sequence[float]], Sequence[float]],
) -> dict[str, tuple[float, ...]]:
    if modality not in modalities:
        raise ValueError(f"unknown modality: {modality}")
    result = {key: tuple(float(x) for x in value) for key, value in modalities.items()}
    result[modality] = tuple(float(x) for x in perturbation(modalities[modality]))
    if not result[modality]:
        raise ValueError("perturbation produced empty modality features")
    return result
