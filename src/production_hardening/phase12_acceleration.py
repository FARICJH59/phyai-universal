from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class TensorRTExecutionResult:
    engine_id: str
    outputs: tuple[float, ...]
    elapsed_ms: float


class TensorRTExecutionAdapter:
    """Explicit TensorRT runtime boundary; requires an injected real engine runner."""

    def __init__(self, engine_runner: Any, engine_id: str) -> None:
        if not engine_id.strip():
            raise ValueError("engine_id is required")
        self.engine_runner = engine_runner
        self.engine_id = engine_id

    def infer(self, inputs: Sequence[float]) -> TensorRTExecutionResult:
        runner = getattr(self.engine_runner, "infer", None)
        if runner is None:
            raise RuntimeError("TensorRT engine runner must expose infer(inputs)")
        result = runner(inputs)
        outputs = tuple(float(x) for x in result.outputs if hasattr(result, "outputs")) if hasattr(result, "outputs") else tuple(float(x) for x in result)
        elapsed_ms = float(result.elapsed_ms) if hasattr(result, "elapsed_ms") else 0.0
        if elapsed_ms < 0:
            raise RuntimeError("TensorRT runtime reported negative elapsed time")
        return TensorRTExecutionResult(self.engine_id, outputs, elapsed_ms)


@dataclass(frozen=True, slots=True)
class CudaExecutionResult:
    kernel_id: str
    outputs: tuple[float, ...]
    elapsed_ms: float


class TimedCudaKernel:
    """Times an injected compiled CUDA kernel without providing a CPU substitute."""

    def __init__(self, kernel: Any, kernel_id: str) -> None:
        if not kernel_id.strip():
            raise ValueError("kernel_id is required")
        self.kernel = kernel
        self.kernel_id = kernel_id

    def run(self, inputs: Sequence[float]) -> CudaExecutionResult:
        runner = getattr(self.kernel, "run", None)
        if runner is None:
            raise RuntimeError("CUDA kernel must expose run(inputs)")
        result = runner(inputs)
        outputs = tuple(float(x) for x in result.outputs if hasattr(result, "outputs")) if hasattr(result, "outputs") else tuple(float(x) for x in result)
        elapsed_ms = float(result.elapsed_ms) if hasattr(result, "elapsed_ms") else 0.0
        if elapsed_ms < 0:
            raise RuntimeError("CUDA runtime reported negative elapsed time")
        return CudaExecutionResult(self.kernel_id, outputs, elapsed_ms)
