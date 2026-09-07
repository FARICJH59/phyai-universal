# Phase 18 — Tamper-Evident Receipt Chain

## Purpose

Phase 18 extends Phase 17 durable receipts into an append-only, tamper-evident receipt chain. Each entry commits to the exact execution identity, attempt, sequence, result digest, and predecessor receipt digest.

## Chain invariant

```text
receipt[n]
  = H(identity_digest | attempt_id | sequence | result_digest | receipt[n-1].chain_digest)
```

The first entry uses an explicit `GENESIS` predecessor marker.

## Fail-closed rules

The reference store and verifier reject:

- predecessor mismatch;
- identity changes within one chain;
- attempt identity changes within one chain;
- sequence replay or regression;
- malformed or tampered chain digests;
- a non-genesis predecessor on the first entry.

## Security boundary

Phase 18 does not create authorization. It operates only on already-established execution identity and evidence. Capability, lease, fence, policy, and admission authority remain owned by HOARE/AEGIS/TCX through the Phase 16–17 boundary.

The in-memory store is a reference implementation only. A production deployment should inject an append-only durable store with transactional uniqueness and an appropriate retention/replication policy.

## Verification status

The Phase 18 workflow is isolated to `tests/unit/test_phase18_receipt_chain.py`. A green CI result is required before treating this phase as verified; no hardware, GPU, Jetson, TensorRT, CUDA, or physical actuator is required for this phase.
