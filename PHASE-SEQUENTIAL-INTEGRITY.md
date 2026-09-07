# Cross-Phase Sequential Integrity

This document defines the conformance spine for PHyAI-Universal phases 1 through 18. It does not replace phase-local tests; it verifies identity, lineage, authority boundaries, and fail-closed sequencing across phase boundaries.

## Canonical sequence

```text
1 Contracts → 2 Sensors → 3 Simulation → 4 Surrogates → 5 Perception
→ 6 Control → 7 Reasoning → 8 Evaluation → 9 Learned World Model
→ 10 Learned Multimodal → 11 ONNX → 12 TensorRT/CUDA → 13 Latency
→ 14 Robustness → 15 Physical/HIL → 16 HOARE/AEGIS/TCX
→ 17 Cryptographic Evidence → 18 Receipt Chain
```

## Invariants

1. Tenant and project identity remain stable across workload phases.
2. Sensor observations preserve source, sequence, timestamp, calibration, confidence, and provenance.
3. Simulation and surrogate layers remain authorization-free.
4. Perception, reasoning, and control produce knowledge or proposals, not physical authority.
5. Control commands preserve scene and observation lineage.
6. Learned-model and acceleration layers require explicit adapters; opaque bytes are not silently treated as tensors or production inference.
7. ONNX, TensorRT, CUDA, latency, and robustness layers are evidence-producing boundaries and are not themselves physical-deployment evidence.
8. Physical actuation requires explicit governed admission.
9. Capability, lease, and fence identifiers originate at the governance boundary.
10. Attempt identity cannot be rebound between proposal, admission, evidence, or receipt.
11. Execution evidence must be verified against signed admission before receipt creation.
12. Receipt chains preserve identity, attempt, sequence, predecessor, and digest integrity.
13. Cross-tenant and cross-project transitions fail closed.
14. Denied authorization stops execution.
15. Replay, stale predecessor, identity drift, artifact drift, and evidence drift fail closed.

## Verification

`tests/test_phase_sequential_integrity.py` is the cross-phase conformance suite. It complements each phase-local unit suite by checking phase-boundary importability, representative Phase 1→7 lineage, and the governed Phase 16→18 execution/evidence path.

This suite is contract-level evidence. It does not claim live hardware, a production HOARE transport, HSM/KMS signing, GPU execution, TensorRT deployment, or a production durable database.

## Advancement rule

Do not advance to a new phase until its phase-local tests pass and the cross-phase conformance suite passes. Production claims require real implementation evidence, not merely an interface or mock.
