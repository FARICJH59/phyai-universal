import pytest

from src.production_hardening.phase12_acceleration import (
    CudaExecutionResult,
    TensorRTExecutionAdapter,
    TensorRTExecutionResult,
    TimedCudaKernel,
)


class Runner:
    def __init__(self, outputs=(1.0, 2.0), elapsed_ms=1.25):
        self.outputs = outputs
        self.elapsed_ms = elapsed_ms

    def infer(self, inputs):
        return self


class Kernel:
    def __init__(self, outputs=(3.0, 4.0), elapsed_ms=0.75):
        self.outputs = outputs
        self.elapsed_ms = elapsed_ms

    def run(self, inputs):
        return self


def test_tensorrt_adapter_preserves_engine_and_outputs():
    result = TensorRTExecutionAdapter(Runner(), "engine-v1").infer((0.0,))
    assert result == TensorRTExecutionResult("engine-v1", (1.0, 2.0), 1.25)


def test_tensorrt_adapter_requires_real_runner():
    with pytest.raises(RuntimeError, match="must expose infer"):
        TensorRTExecutionAdapter(object(), "engine-v1").infer((0.0,))


def test_cuda_adapter_preserves_kernel_and_outputs():
    result = TimedCudaKernel(Kernel(), "kernel-v1").run((0.0,))
    assert result == CudaExecutionResult("kernel-v1", (3.0, 4.0), 0.75)


def test_cuda_adapter_requires_real_kernel():
    with pytest.raises(RuntimeError, match="must expose run"):
        TimedCudaKernel(object(), "kernel-v1").run((0.0,))


def test_acceleration_rejects_negative_runtime_measurement():
    with pytest.raises(RuntimeError, match="negative elapsed"):
        TensorRTExecutionAdapter(Runner(elapsed_ms=-1.0), "engine-v1").infer((0.0,))
    with pytest.raises(RuntimeError, match="negative elapsed"):
        TimedCudaKernel(Kernel(elapsed_ms=-1.0), "kernel-v1").run((0.0,))
