from src.production_hardening.cuda import CudaKernelAdapter, CudaKernelConfig
from src.production_hardening.inference_backends import (
    CallableBackend,
    ModelInputSpec,
    benchmark_backend,
    build_benchmark_input,
    load_tensorrt_backend,
)
from src.production_hardening.vggt_backend import VGGTBackend


def test_callable_backend_benchmark_is_measurable():
    backend = CallableBackend("reference", lambda values: tuple(x + 1 for x in values))
    result = benchmark_backend(backend, [1.0, 2.0], iterations=3)
    assert result.outputs == (2.0, 3.0)
    assert result.elapsed_ms >= 0.0


def test_model_aware_benchmark_input_preserves_shape_and_dtype():
    spec = ModelInputSpec("input", (1, None, 3), "tensor(float)")
    tensor = build_benchmark_input(spec, dynamic_dimension=4)
    assert tensor.shape == (1, 4, 3)
    assert str(tensor.dtype) == "float32"


def test_model_aware_benchmark_input_rejects_unknown_type():
    spec = ModelInputSpec("input", (1, 3), "tensor(string)")
    try:
        build_benchmark_input(spec)
    except RuntimeError as exc:
        assert "Unsupported ONNX input type" in str(exc)
    else:
        raise AssertionError("Unknown ONNX input types must fail explicitly")


def test_vggt_backend_requires_real_injected_predictor():
    class Predictor:
        def predict(self, values):
            return ("scene", len(values))

    assert VGGTBackend(Predictor()).predict([1, 2]) == ("scene", 2)


def test_cuda_adapter_requires_explicit_kernel():
    class Kernel:
        def run(self, values):
            return [x * 2 for x in values]

    adapter = CudaKernelAdapter(Kernel(), CudaKernelConfig("example"))
    assert adapter.run([1, 2]) == (2.0, 4.0)


def test_tensorrt_never_silently_falls_back_to_fake_execution():
    try:
        load_tensorrt_backend("engine.plan")
    except RuntimeError as exc:
        assert "TensorRT" in str(exc)
    else:
        raise AssertionError("TensorRT loader must require a real device adapter")
