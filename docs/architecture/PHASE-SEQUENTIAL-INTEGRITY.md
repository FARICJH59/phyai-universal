# Phase Sequential Integrity

## Purpose

This integration gate verifies that PHyAI-Universal behaves as one ordered system rather than as independent modules.

**Important:** implementation phase numbers describe build progression; they do not imply that runtime execution is a simple numeric sequence. The runtime graph is governed by data and authority dependencies.

## Runtime dependency graph

```text
                         PHASE 1
                        Contracts
                           |
                           v
                         PHASE 2
                         Sensors
                           |
                           v
                         PHASE 5
                       Perception
                           |
                           v
                         PHASE 7
                        Reasoning
                           |
            +--------------+--------------+
            |              |              |
            v              v              v
        PHASE 3        PHASE 9         PHASE 10
       Simulation    Learned World     Learned
            |           Model         Multimodal
            v              |              |
        PHASE 4            +------+-------+
       Surrogates                 |
            |                     |
            +----------+----------+
                       v
                    PHASE 6
                     Control
                  (proposal only)
                       |
                       v
                    PHASE 8
                   Evaluation
                       |
                       v
              PHASES 11-14
       ONNX -> TensorRT/CUDA ->
       Latency -> Robustness
                       |
                       v
                    PHASE 15
                   Physical/HIL
                       |
                       v
                    PHASE 16
                HOARE/AEGIS/TCX
              AUTHORITY BOUNDARY
                       |
                       v
                    PHASE 17
            Cryptographic Evidence
                       |
                       v
                    PHASE 18
                 Receipt Chain
```

The integration test therefore follows the runtime dependency graph rather than pretending that `6 -> 7` is the execution order merely because Phase 6 was implemented before Phase 7.

## Invariants

### Identity continuity

Tenant and project identity must remain constant across the applicable pipeline. Scene identity must remain bound to its source observations. Control commands must preserve scene and observation lineage. Attempt identity must remain stable from proposal through governed execution and evidence.

### Authority ordering

Phases 1-15 may create contracts, observations, scenes, plans, simulation results, surrogate results, learned-model outputs, runtime artifacts, measurements, robustness results, or physical I/O boundaries. They do **not** mint execution authority.

Phase 16 is the authority boundary. Capability, lease, and fence identifiers must originate from the accepted governed admission returned by the HOARE transport.

### Evidence ordering

Phase 17 derives execution identity from accepted Phase 16 admission, cryptographically binds the command, attempt, artifact, capability, lease, fence, and policy digest, signs that identity, verifies execution evidence, and only then creates a durable receipt through `commit_verified_evidence()`.

### Physical ordering

Phase 15 defines the physical/HIL adapter, but physical execution must occur only after Phase 16 governance has admitted the exact execution identity. Defining a physical adapter is not equivalent to granting authority.

### Receipt continuity

Phase 18 links the verified receipt identity, attempt, sequence, and result digest into an append-only hash chain. Tampering, predecessor changes, identity changes, attempt changes, or sequence regression must fail closed.

## Regression cases

The architecture gate must reject at least:

- cross-tenant observations entering perception;
- cross-project identity changes;
- scene/observation lineage loss;
- reasoning results claiming authorization;
- control proposals carrying execution authority;
- mismatched artifact or command identity at Phase 16;
- denied Phase 16 admission entering Phase 17;
- admission attempt rebinding;
- evidence with a different device, attempt, identity digest, or admission signature;
- receipt creation without successful evidence verification;
- receipt-chain predecessor, identity, attempt, or sequence tampering.

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
