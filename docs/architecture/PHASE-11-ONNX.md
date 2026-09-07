# Phase 11 — PyTorch to ONNX Integration

Phase 11 establishes a real ONNX artifact validation and numerical parity boundary for learned Physical AI models.

## Pipeline

`PyTorch model → ONNX artifact → ONNX Runtime → parity validation → latency measurement`

The existing `PyTorchONNXExporter` remains the actual export adapter and requires PyTorch at runtime. Phase 11 adds validation of a real ONNX artifact through ONNX Runtime and a strict output-parity helper.

## Fail-closed rules

- missing or empty ONNX artifacts are rejected;
- models without inputs are rejected;
- output length mismatches are rejected;
- numerical error above the declared tolerance is rejected;
- ONNX Runtime is an explicit dependency of runtime validation, not silently emulated.

## Evidence boundary

CI validates the contract without requiring an installed ONNX model. A passing contract test is not evidence of successful export or hardware inference.

Not yet claimed:

- a trained production Physical AI model exported successfully;
- GPU ONNX Runtime execution;
- TensorRT conversion;
- CUDA kernel acceleration;
- Jetson performance;
- sub-50-ms end-to-end control latency.

Those claims require real artifacts and measurements.
