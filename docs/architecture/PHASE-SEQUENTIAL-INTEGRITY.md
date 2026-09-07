# Phase Sequential Integrity

## Purpose

This integration gate verifies that the PHyAI-Universal phase architecture behaves as one ordered system rather than as independent modules.

The verified spine is:

```text
1 Contracts
  -> 2 Sensors
  -> 3 Simulation
  -> 4 Surrogates
  -> 5 Perception
  -> 6 Control
  -> 7 Reasoning
  -> 8 Evaluation
  -> 9 Learned World Model
  -> 10 Learned Multimodal
  -> 11 ONNX
  -> 12 TensorRT/CUDA
  -> 13 Latency
  -> 14 Robustness
  -> 15 Physical/HIL
  -> 16 HOARE/AEGIS/TCX
  -> 17 Cryptographic Evidence
  -> 18 Receipt Chain
```

## Invariants

The integration test verifies four architectural properties.

### Identity continuity

Tenant, project, scene, observation, command, and attempt identities are preserved at every applicable domain boundary. A later phase cannot silently substitute an earlier identity.

### Authority ordering

Phases 1-15 produce contracts, models, plans, proposals, evaluation results, runtime artifacts, robustness results, or physical I/O boundaries. They do not mint execution authority.

Phase 16 is the authority boundary. Capability, lease, and fence identifiers must come from the governed admission returned by the HOARE transport.

### Evidence ordering

Phase 17 derives cryptographic execution identity from accepted Phase 16 admission, signs that identity, verifies execution evidence, and only then creates a durable receipt through `commit_verified_evidence()`.

### Receipt continuity

Phase 18 links the durable receipt identity, attempt, sequence, and result digest into an append-only hash chain. Tampering or predecessor/identity/sequence changes must fail closed.

## Scope and limitations

This is an architecture-level conformance gate using deterministic/reference backends and injected runtime adapters. It does **not** claim:

- live production HOARE/AEGIS/TCX deployment;
- real TensorRT or CUDA hardware execution;
- Jetson benchmark results;
- physical sim-to-real validation;
- production HSM/KMS signing;
- production durable database guarantees.

Those claims require their respective real infrastructure and hardware evidence.

## Gate policy

No Phase 19 implementation should be treated as architecturally complete until this sequential-integrity test passes in CI together with the individual phase tests.
