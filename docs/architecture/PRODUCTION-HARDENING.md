# Production Hardening

The PHyAI-Universal workload phases establish the domain pipeline. This layer adds concrete model, trajectory, multimodal, deployment, robustness, and HOARE-boundary capabilities without creating a second authority plane.

## World modeling and trajectories

`production_hardening.world_model` defines an action-conditioned world-model contract. `ActionConditionedReferenceWorldModel` is deterministic and exists for contract tests and benchmarks; it is **not** a learned diffusion model. `AutoregressiveTrajectoryGenerator` performs sequential rollout through the model boundary. Learned transformer, diffusion, or video-prediction implementations can replace the reference backend.

## Multimodal representation

`production_hardening.multimodal` accepts RGB, depth, proprioception, tactile, and language inputs and produces a deterministic unified representation boundary. The reference implementation uses content digests, not a fabricated learned latent space. A learned multimodal encoder is an explicit backend replacement.

## Spatial perception

`production_hardening.vggt_backend` provides an explicit adapter for a real VGGT-compatible predictor. The existing Phase-5 deterministic predictor remains a contract-test implementation; it is not mislabeled as VGGT inference.

## Inference optimization

`production_hardening.export` provides a real PyTorch `torch.onnx.export` adapter. `production_hardening.inference_backends` provides an ONNX Runtime loader and latency benchmark. The ONNX benchmark derives its input tensor from the model's declared name, shape, and element type. TensorRT is deliberately fail-explicit until a real TensorRT engine/device adapter is supplied. `production_hardening.cuda` defines the explicit custom-kernel boundary; it does not pretend Python execution is CUDA acceleration.

## Latency and hardware

`configs/hardware/jetson.yaml` defines NVIDIA Jetson as a deployment target with TensorRT as the primary runtime and ONNX Runtime as fallback. The 50 ms requirement is a target, not a claimed result. `benchmark_backend` measures actual runtime latency on the machine/device used for the benchmark. A real model must be supplied to the benchmark; the tool does not invent a compatible input shape.

## Sim-to-real robustness

`production_hardening.robustness` supports measurable evaluation layers: byte-level perturbation detection, numeric output sensitivity, trajectory deviation, and named-modality perturbation. Output sensitivity reports L2 delta, relative delta, and confidence degradation. Trajectory evaluation reports mean/max L2 deviation, sample count, and confidence degradation. `MultimodalPerturbation` can perturb a selected RGB, depth, proprioception, tactile, or language payload while leaving other modality payloads unchanged.

These are evaluation primitives, not claims of physical robustness. Real sensor captures, learned-model outputs, hardware-in-the-loop runs, and sim-to-real trials are still required before making physical deployment performance claims.

## HOARE boundary

`production_hardening.hoare_boundary` is the only physical-execution handoff. PHyAI submits a `ControlCommand` proposal plus artifact/policy context. PHyAI does not mint authorization, capabilities, leases, fences, dispatch identities, or execution receipts. Tenant/project mismatches fail closed before the external admission client is called.

## Capability status

| Capability | Status |
|---|---|
| Action-conditioned world-model contract | Implemented |
| Autoregressive rollout boundary | Implemented |
| RGB/depth/proprioception/tactile/language fusion boundary | Implemented |
| VGGT-compatible backend adapter | Implemented; real model injection required |
| PyTorch → ONNX adapter | Implemented; PyTorch required |
| ONNX Runtime adapter | Implemented; model-aware input construction |
| TensorRT execution | Explicit device-runtime integration required |
| Custom CUDA kernels | Explicit compiled-kernel integration required |
| Jetson deployment target | Defined |
| 50 ms latency target | Benchmark target; not claimed achieved |
| Output sensitivity evaluation | Implemented |
| Trajectory deviation evaluation | Implemented |
| Multimodal perturbation harness | Implemented |
| Physical sim-to-real robustness | Not yet demonstrated; HIL evidence required |
| Physical execution governance | HOARE boundary defined |
