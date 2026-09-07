from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class ONNXArtifactMetadata:
    path: str
    size_bytes: int
    input_name: str
    input_shape: tuple[int | None, ...]
    input_type: str


@dataclass(frozen=True, slots=True)
class InferenceParityResult:
    max_absolute_error: float
    mean_absolute_error: float
    samples: int


class ONNXArtifactValidator:
    """Validates a real ONNX artifact through ONNX Runtime when available."""

    def inspect(self, model_path: str) -> ONNXArtifactMetadata:
        path = Path(model_path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("ONNX artifact must exist and be non-empty")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("onnxruntime is required for ONNX artifact validation") from exc
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        if not session.get_inputs():
            raise RuntimeError("ONNX model has no inputs")
        item = session.get_inputs()[0]
        shape = tuple(dim if isinstance(dim, int) else None for dim in item.shape)
        return ONNXArtifactMetadata(str(path), path.stat().st_size, item.name, shape, item.type)


def compare_outputs(reference: Sequence[float], candidate: Sequence[float], tolerance: float = 1e-4) -> InferenceParityResult:
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if not reference or not candidate:
        raise ValueError("outputs must not be empty")
    if len(reference) != len(candidate):
        raise ValueError("reference and candidate output lengths must match")
    errors = [abs(float(a) - float(b)) for a, b in zip(reference, candidate)]
    result = InferenceParityResult(max(errors), sum(errors) / len(errors), len(errors))
    if result.max_absolute_error > tolerance:
        raise ValueError(
            f"ONNX output parity exceeded tolerance: max_absolute_error={result.max_absolute_error} tolerance={tolerance}"
        )
    return result
