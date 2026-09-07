# Phase 9 — Learned World-Model Integration

Phase 9 introduces the real learned-model integration boundary required for action-conditioned physical-AI world modeling.

## Scope

The phase establishes four explicit layers:

1. **Temporal domain input** — ordered video/RGB-D frames plus action conditions and a rollout horizon.
2. **Representation encoding** — an injected encoder converts opaque sensor payloads into numeric frame features and action vectors.
3. **Learned inference** — an injected model consumes temporal frame/action tensors and predicts a horizon of future state vectors.
4. **Canonical rollout** — the adapter converts model output into the existing `WorldModelRollout` contract while preserving tenant, project, and scene identity.

## Action-conditioned interface

The concrete PyTorch bridge expects:

- frame features shaped `[batch, time, frame_features]`
- action features shaped `[batch, horizon, action_features]`
- output shaped `[batch, horizon, state_features]`

`PyTorchTensorModel` is a runtime bridge, not a pretrained model. Production callers must supply the actual trained `torch.nn.Module`, weights, device, and feature encoder.

## Fail-closed rules

- Empty temporal inputs are rejected.
- Empty action inputs are rejected.
- Non-positive horizons are rejected.
- Learned models must expose a stable non-empty `model_id`.
- Opaque image bytes are never silently cast into tensors.
- Model output length must exactly equal the requested horizon.
- Empty output rows are rejected.
- No authorization, capability, lease, fence, dispatch, or actuation field exists in the learned-model contract.
- The existing compatibility adapter still refuses to invent a mapping from canonical simulation state to learned representation.

## What this phase does not claim

This phase does **not** claim a pretrained diffusion world model, pretrained video model, VGGT weights, TensorRT engine, CUDA kernel, Jetson benchmark, physical hardware-in-the-loop validation, or sub-50-ms end-to-end control latency.

Those require real model artifacts, target hardware, and measured evidence.

## HOARE boundary

Learned inference produces predictions. Predictions can inform simulation, evaluation, and control proposals, but they do not authorize physical execution. Any physical side effect remains subject to the existing HOARE/AEGIS/TCX governance boundary.
