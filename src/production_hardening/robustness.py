from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RobustnessCase:
    name: str
    perturbation: Callable[[bytes], bytes]


@dataclass(frozen=True, slots=True)
class RobustnessResult:
    name: str
    baseline_digest: str
    perturbed_digest: str
    changed: bool


@dataclass(frozen=True, slots=True)
class OutputSensitivity:
    l2_delta: float
    relative_delta: float
    baseline_confidence: float
    perturbed_confidence: float
    confidence_degradation: float


@dataclass(frozen=True, slots=True)
class TrajectoryDeviation:
    mean_l2_error: float
    maximum_l2_error: float
    samples: int
    baseline_confidence: float
    perturbed_confidence: float
    confidence_degradation: float


@dataclass(frozen=True, slots=True)
class MultimodalPerturbation:
    modality: str
    case: RobustnessCase


class SensorNoiseHarness:
    """Deterministic perturbation and model-sensitivity harness for sim-to-real evaluation."""

    @staticmethod
    def bit_flip(mask: int = 1) -> RobustnessCase:
        if not 0 <= mask <= 255:
            raise ValueError("mask must be between 0 and 255")

        def perturb(payload: bytes) -> bytes:
            if not payload:
                raise ValueError("payload must not be empty")
            data = bytearray(payload)
            data[0] ^= mask
            return bytes(data)

        return RobustnessCase("bit-flip", perturb)

    @staticmethod
    def evaluate(payload: bytes, case: RobustnessCase) -> RobustnessResult:
        if not payload:
            raise ValueError("payload must not be empty")
        baseline = sha256(payload).hexdigest()
        perturbed = sha256(case.perturbation(payload)).hexdigest()
        return RobustnessResult(case.name, baseline, perturbed, baseline != perturbed)

    @staticmethod
    def evaluate_output(
        baseline: Sequence[float],
        perturbed: Sequence[float],
        baseline_confidence: float,
        perturbed_confidence: float,
    ) -> OutputSensitivity:
        if not baseline or not perturbed:
            raise ValueError("baseline and perturbed outputs must not be empty")
        if len(baseline) != len(perturbed):
            raise ValueError("baseline and perturbed outputs must have equal length")
        for confidence in (baseline_confidence, perturbed_confidence):
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0 and 1")
        delta = sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(baseline, perturbed)))
        norm = sqrt(sum(float(a) ** 2 for a in baseline))
        return OutputSensitivity(
            l2_delta=delta,
            relative_delta=delta / max(norm, 1e-12),
            baseline_confidence=baseline_confidence,
            perturbed_confidence=perturbed_confidence,
            confidence_degradation=max(0.0, baseline_confidence - perturbed_confidence),
        )

    @staticmethod
    def evaluate_trajectory(
        baseline: Sequence[Mapping[str, float]],
        perturbed: Sequence[Mapping[str, float]],
        baseline_confidence: float,
        perturbed_confidence: float,
    ) -> TrajectoryDeviation:
        if not baseline or not perturbed:
            raise ValueError("baseline and perturbed trajectories must not be empty")
        if len(baseline) != len(perturbed):
            raise ValueError("baseline and perturbed trajectories must have equal length")
        for confidence in (baseline_confidence, perturbed_confidence):
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0 and 1")
        errors: list[float] = []
        for expected, actual in zip(baseline, perturbed):
            if set(expected) != set(actual):
                raise ValueError("trajectory state keys must match")
            errors.append(sqrt(sum((float(expected[k]) - float(actual[k])) ** 2 for k in expected)))
        return TrajectoryDeviation(
            mean_l2_error=sum(errors) / len(errors),
            maximum_l2_error=max(errors),
            samples=len(errors),
            baseline_confidence=baseline_confidence,
            perturbed_confidence=perturbed_confidence,
            confidence_degradation=max(0.0, baseline_confidence - perturbed_confidence),
        )

    @staticmethod
    def perturb_modalities(
        modalities: Mapping[str, bytes],
        perturbations: Sequence[MultimodalPerturbation],
    ) -> dict[str, bytes]:
        result = dict(modalities)
        for perturbation in perturbations:
            if not perturbation.modality.strip():
                raise ValueError("modality must not be empty")
            if perturbation.modality not in result:
                raise ValueError(f"unknown modality: {perturbation.modality}")
            result[perturbation.modality] = perturbation.case.perturbation(result[perturbation.modality])
        return result
