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


@dataclass(frozen=True, slots=True)
class ModelInputSpec:
    """Runtime input metadata needed to construct a valid benchmark tensor."""

    name: str
    shape: tuple[int | None, ...]
    element_type: str


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


def build_benchmark_input(spec: ModelInputSpec, dynamic_dimension: int = 1) -> object:
    """Build a zero-valued NumPy tensor matching a real model's first input."""
    if dynamic_dimension <= 0:
        raise ValueError("dynamic_dimension must be positive")
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required to construct an ONNX benchmark input") from exc

    shape = tuple(dynamic_dimension if dim is None or dim <= 0 else dim for dim in spec.shape)
    if not shape:
        raise RuntimeError(f"ONNX input {spec.name!r} has no tensor shape")

    dtype_map: Mapping[str, object] = {
        "tensor(float)": np.float32,
        "tensor(double)": np.float64,
        "tensor(float16)": np.float16,
        "tensor(int64)": np.int64,
        "tensor(int32)": np.int32,
        "tensor(int16)": np.int16,
        "tensor(int8)": np.int8,
        "tensor(uint64)": np.uint64,
        "tensor(uint32)": np.uint32,
        "tensor(uint16)": np.uint16,
        "tensor(uint8)": np.uint8,
        "tensor(bool)": np.bool_,
    }
    try:
        dtype = dtype_map[spec.element_type]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported ONNX input type: {spec.element_type}") from exc
    return np.zeros(shape, dtype=dtype)


def load_onnx_runtime_backend(model_path: str) -> InferenceBackend:
    """Create a real ONNX Runtime backend when the optional dependency is installed."""
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("onnxruntime is required for the ONNX Runtime backend") from exc
    session = ort.InferenceSession(model_path, providers=ort.get_available_providers())
    input_meta = session.get_inputs()[0]
    spec = ModelInputSpec(
        name=input_meta.name,
        shape=tuple(dim if isinstance(dim, int) else None for dim in input_meta.shape),
        element_type=input_meta.type,
    )

    class ONNXRuntimeBackend:
        backend_id = "onnxruntime"
        input_spec = spec

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
