# Phase 10 — Learned Multimodal Representation

## Scope

Phase 10 replaces the deterministic multimodal representation boundary with an explicit learned-encoder boundary. It supports RGB, depth, proprioception, tactile, and language inputs without pretending that opaque domain payloads are model-ready tensors.

## Contract

`ModalityInput` remains the domain-level input. `ModalityEncoder` converts one domain modality into a validated `TensorModalityInput`. `LearnedMultimodalEncoder` receives only numeric modality representations and produces `LearnedMultimodalRepresentation`.

The bridge enforces:

- tenant and project identity preservation;
- temporal ordering preservation;
- modality identity preservation;
- confidence bounds;
- explicit encoder registration;
- fail-closed behavior for unknown modalities or identity mutation.

## Model boundary

The learned fusion implementation is injected through `LearnedMultimodalEncoder`. This repository does not claim a pretrained vision-language, RGB-D, tactile, or proprioceptive model until concrete model weights and runtime integration are supplied.

A production implementation may use PyTorch, JAX, ONNX Runtime, TensorRT, or another validated backend while preserving this contract.

## Relationship to Phase 9

Phase 9 defines the learned temporal world-model boundary. Phase 10 supplies the learned multimodal representation that can feed that temporal model. The composition is:

`raw modalities → modality encoders → learned multimodal representation → temporal world model → action-conditioned rollout`.

## Authority boundary

The representation is predictive input, not authority. Learned multimodal inference cannot authorize, mint capabilities, create leases, establish fences, dispatch actuation, or create execution receipts. Physical side effects remain governed by HOARE through its admission and execution contracts.

## Evidence status

Implemented:

- learned multimodal interface;
- explicit per-modality encoder boundary;
- deterministic contract-test backend;
- tenant/project and modality fail-closed checks;
- isolated Phase 10 CI.

Not claimed yet:

- pretrained multimodal weights;
- production RGB/depth/tactile/proprioceptive/language encoders;
- GPU inference;
- TensorRT execution;
- Jetson benchmark;
- sub-50-ms end-to-end control loop;
- physical hardware-in-the-loop validation.
