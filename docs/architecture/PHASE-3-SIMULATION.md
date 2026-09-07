# Phase 3 — Simulation

Phase 3 provides a deterministic, hardware-neutral simulation boundary for PHyAI-Universal.

## Responsibilities

- Generate reproducible scenarios from tenant/project identity and a seed.
- Represent simulation state independently of physical hardware.
- Evaluate candidate actions deterministically.
- Preserve tenant and project isolation across simulation state transitions.
- Produce diagnostics and rewards for planning/evaluation workloads.

## Authority boundary

A `SimulationAction` is simulator-local. It has no lease, capability, authorization, or actuation authority.

A simulation result is evidence about a hypothetical execution, not evidence that a physical action occurred.

The production path remains:

`PHyAI proposal → explicit HOARE adapter → HOARE execution contract → governed authorization → physical execution`.

Simulation must never bypass that boundary.

## Determinism

The reference generator derives scenario identity and initial state deterministically from `(tenant_id, project_id, environment_id, seed)`. The reference environment contains no external randomness, network dependency, clock dependency, or hardware dependency.

## Extension point

The reference environment is intentionally small. Domain-specific simulators can implement the same semantic boundary without changing Phase 1 contracts. Physics engines, robotics simulators, and digital twins belong behind this environment interface and are not required for the Phase 3 contract tests.
