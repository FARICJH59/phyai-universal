from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Callable, Mapping, Protocol, Sequence


class InferenceBackend(Protocol):
    backend_id: str
    def infer(self, inputs: Sequence[float]) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class BackendResult:
    backend_id: str
    outputs: Sequence[float]
    elapsed_ms: float


class CallableBackend:
    """Benchmarkable backend wrapper for a real inference callable."""

    def __init__(self, backend_id: str, fn: Callable[[Sequence[float]], Sequence[float]]) -> None:
        if not backend_id.strip():
            raise ValueError("backend_id is required")
        self.backend_id = backend_id
        self._fn = fn

    def infer(self, inputs: Sequence[float]) -> Sequence[float]:
        return self._fn(inputs)


def benchmark_backend(
    backend: InferenceBackend,
    inputs: Sequence[float],
    iterations: int = 100,
) -> BackendResult:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    start = perf_counter_ns()
    outputs: Sequence[float] = ()
    for _ in range(iterations):
        outputs = backend.infer(inputs)
    elapsed_ms = (perf_counter_ns() - start) / 1_000_000 / iterations
    return BackendResult(backend.backend_id, tuple(outputs), elapsed_ms)


def load_onnx_runtime_backend(model_path: str) -> InferenceBackend:
    """Create a real ONNX Runtime backend when the optional dependency is installed."""
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("onnxruntime is required for the ONNX Runtime backend") from exc
    session = ort.InferenceSession(model_path, providers=ort.get_available_providers())
    input_meta = session.get_inputs()[0]

    class ONNXRuntimeBackend:
        backend_id = "onnxruntime"
        def infer(self, inputs: Sequence[float]) -> Sequence[float]:
            result = session.run(None, {input_meta.name: inputs})
            return tuple(float(x) for x in result[0].ravel())

    return ONNXRuntimeBackend()


def load_tensorrt_backend(engine_path: str) -> InferenceBackend:
    """Fail explicitly until TensorRT bindings are available; never emulate TensorRT."""
    raise RuntimeError(
        "TensorRT backend requires a built TensorRT engine and a device-specific runtime adapter; "
        f"engine={engine_path!r}"
    )
