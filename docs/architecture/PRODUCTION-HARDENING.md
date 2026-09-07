# Production Hardening

The eight PHyAI-Universal workload phases establish the domain pipeline. This layer adds the concrete capability boundaries needed for physical-AI deployment without creating a second authority plane.

## World modeling and trajectories

`production_hardening.world_model` defines an action-conditioned world-model contract. `ActionConditionedReferenceWorldModel` is deterministic and exists for contract tests and benchmarks; it is not represented as a learned diffusion model. `AutoregressiveTrajectoryGenerator` performs sequential rollout through the model boundary. Learned transformer, diffusion, or video-prediction implementations can replace the reference backend.

## Multimodal representation

`production_hardening.multimodal` accepts RGB, depth, proprioception, tactile, and language inputs and produces a deterministic unified representation boundary. The reference implementation uses content digests, not a fabricated learned latent space. A learned multimodal encoder is an explicit backend replacement.

## Inference optimization

`production_hardening.export` provides a real PyTorch `torch.onnx.export` adapter. `production_hardening.inference_backends` provides an ONNX Runtime loader and a benchmark function. TensorRT is deliberately fail-explicit until a real TensorRT engine/device adapter is supplied; no mock TensorRT performance is reported.

## Latency and hardware

`configs/hardware/jetson.yaml` defines NVIDIA Jetson as a deployment target with TensorRT as the primary runtime and ONNX Runtime as fallback. The 50 ms requirement is a target, not a claimed result. `benchmark_backend` measures elapsed inference time on the actual runtime/device used by the test.

## Sim-to-real robustness

`production_hardening.robustness` provides deterministic sensor perturbation cases. It is a harness for measuring model sensitivity; it does not claim physical robustness until real sensor captures and hardware-in-the-loop results are supplied.

## HOARE boundary

`production_hardening.hoare_boundary` is the only physical-execution handoff. PHyAI submits a `ControlCommand` proposal plus artifact/policy context. PHyAI does not mint authorization, capabilities, leases, fences, dispatch identities, or execution receipts. Tenant/project mismatches fail closed before the external admission client is called.

## Capability status

| Capability | Status |
|---|---|
| Action-conditioned model contract | Implemented |
| Autoregressive rollout boundary | Implemented |
| RGB/depth/proprioception/tactile/language fusion boundary | Implemented |
| PyTorch → ONNX adapter | Implemented when PyTorch is installed |
| ONNX Runtime adapter | Implemented when ONNX Runtime is installed |
| TensorRT execution | Explicit device-runtime integration required |
| Custom CUDA kernels | Explicit kernel implementation required |
| Jetson deployment target | Defined |
| 50 ms latency target | Benchmark target; not claimed achieved |
| Sim-to-real/noise harness | Implemented |
| Physical execution governance | HOARE boundary defined |
