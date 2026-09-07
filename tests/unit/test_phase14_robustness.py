import pytest

from src.production_hardening.phase14_robustness import (
    RobustnessThreshold,
    SimToRealRobustnessHarness,
    perturb_modalities,
)


def evaluate(**kwargs):
    return SimToRealRobustnessHarness(RobustnessThreshold()).evaluate(
        modality="rgb", baseline_output=(1.0, 2.0), perturbed_output=kwargs.get("output", (1.01, 2.01)),
        baseline_trajectory=((0.0, 0.0), (1.0, 1.0)),
        perturbed_trajectory=kwargs.get("trajectory", ((0.01, 0.0), (1.01, 1.0))), confidence=kwargs.get("confidence", 0.95),
    )


def test_robustness_passes_small_perturbation():
    result = evaluate()
    assert result.passed
    assert result.reason == "within_robustness_thresholds"


def test_robustness_fails_closed_on_low_confidence():
    result = evaluate(confidence=0.79)
    assert not result.passed
    assert result.reason == "confidence_below_safety_threshold"


def test_robustness_fails_on_output_sensitivity():
    result = evaluate(output=(2.0, 4.0))
    assert not result.passed
    assert result.reason == "output_sensitivity_exceeded"


def test_robustness_fails_on_trajectory_deviation():
    result = evaluate(trajectory=((1.0, 1.0), (2.0, 2.0)))
    assert not result.passed
    assert result.reason == "trajectory_deviation_exceeded"


def test_modality_perturbation_preserves_other_modalities():
    result = perturb_modalities({"rgb": (1.0, 2.0), "depth": (3.0,)}, "rgb", lambda x: (x[0] + 1, x[1]))
    assert result["rgb"] == (2.0, 2.0)
    assert result["depth"] == (3.0,)


def test_unknown_modality_fails_closed():
    with pytest.raises(ValueError, match="unknown modality"):
        perturb_modalities({"rgb": (1.0,)}, "tactile", lambda x: x)
