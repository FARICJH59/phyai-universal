# Phase 12 — TensorRT and CUDA Acceleration

Phase 12 establishes explicit execution boundaries for hardware-accelerated learned-model inference.

## Boundaries

`ONNX artifact → TensorRT engine runner → accelerated inference`

`tensor workload → compiled CUDA kernel → accelerated kernel execution`

Both paths require injected, real runtime implementations. The repository does not emulate TensorRT or CUDA with CPU code and does not label a generic callable as hardware acceleration.

## Contract guarantees

- TensorRT engine identity is explicit.
- CUDA kernel identity is explicit.
- Outputs are normalized to numeric tuples.
- Runtime measurements cannot be negative.
- Missing runtime methods fail closed.

## Evidence boundary

Phase 12 contract tests use injected test doubles only to verify the adapter boundary. They do **not** constitute evidence that TensorRT or CUDA executed.

Still requiring real hardware evidence:

- built TensorRT engine;
- NVIDIA runtime/device execution;
- compiled CUDA extension/kernel;
- Jetson deployment;
- measured accelerator latency;
- end-to-end control-loop latency below the configured target.

Physical actuation authority remains outside this layer and belongs to HOARE/AEGIS/TCX.
