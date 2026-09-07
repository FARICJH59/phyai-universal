# PHyAI-Universal

Production-oriented Physical AI workload architecture designed to run beneath the HOARE trusted execution plane.

## Phase 1 — Contracts

Phase 1 establishes the domain boundary before runtime implementations are added.

### Canonical contracts

- `SensorObservation` — immutable observation with tenant/project identity, source sequence, timestamp, calibration, confidence, and provenance.
- `SpatialScene` — derived spatial representation linked back to source observations.
- `ControlCommand` — proposed physical action with target, parameters, safety preconditions, scene/evidence lineage, and attempt identity.

A `ControlCommand` is **never authorization**. PHyAI can propose an action; HOARE/AEGIS decides whether that action may produce a governed physical side effect.

### Contract invariants

- tenant and project identity are explicit;
- timestamps are timezone-aware and normalized to UTC;
- sequences are non-negative;
- confidence is bounded to `[0, 1]`;
- observations and scenes require provenance/source lineage;
- control commands require safety preconditions and evidence lineage;
- authority, leases, fences, and execution credentials are deliberately absent from PHyAI domain messages.

## Architecture boundary

```text
Sensors → Perception → Reasoning → Simulation/Surrogates
                                      │
                                      ▼
                               Control Proposal
                                      │
                                      ▼
                              HOARE / AEGIS
                                      │
                             Authority / Lease
                                      │
                                      ▼
                                HYDRA-EDGE
                                      │
                                  Actuation
                                      │
                              Evidence / Verify
```

Phase 2 begins only after the Phase 1 contract suite is green.
