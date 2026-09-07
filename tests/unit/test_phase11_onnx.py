from pathlib import Path

import pytest

from src.production_hardening.phase11_onnx import ONNXArtifactValidator, compare_outputs


def test_output_parity_passes_within_tolerance():
    result = compare_outputs((1.0, 2.0, 3.0), (1.00001, 2.0, 2.99999), tolerance=1e-4)
    assert result.samples == 3
    assert result.max_absolute_error <= 1e-4


def test_output_parity_fails_closed_outside_tolerance():
    with pytest.raises(ValueError, match="parity exceeded tolerance"):
        compare_outputs((1.0,), (1.01,), tolerance=1e-4)


def test_output_parity_rejects_length_mismatch():
    with pytest.raises(ValueError, match="lengths must match"):
        compare_outputs((1.0,), (1.0, 2.0))


def test_validator_rejects_missing_artifact(tmp_path: Path):
    with pytest.raises(ValueError, match="exist and be non-empty"):
        ONNXArtifactValidator().inspect(str(tmp_path / "missing.onnx"))
