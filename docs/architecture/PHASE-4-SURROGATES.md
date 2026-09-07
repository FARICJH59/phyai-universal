# Phase 4 — Surrogates

Phase 4 introduces solver and surrogate boundaries for turning simulated state into candidate solutions.

## Components

- `SolverRequest`: tenant/project/scenario-scoped optimization input.
- `SurrogateSolver`: framework-neutral solver protocol.
- `CandidateSolution`: candidate values plus objective and confidence.
- `SurrogateCompiler`: deterministic conversion of candidate values into a content-addressed artifact.
- `CompiledSurrogate`: immutable artifact metadata and hash.

## Isolation

Solver requests must use simulation state belonging to the same tenant, project, and scenario. This prevents optimization workloads from accidentally crossing workload boundaries.

## Determinism

The reference solver is deterministic. The compiler canonicalizes keys and values before hashing, so equivalent mappings produce identical artifacts.

## Authority boundary

Neither candidate solutions nor compiled surrogate artifacts carry authorization, capability, lease, or actuation authority. They are computational outputs.

A compiled artifact is not proof of physical execution. Physical execution remains exclusively downstream of the HOARE governed execution boundary.

## Framework neutrality

No PyTorch, ONNX, CUDA, TensorRT, or vendor runtime is required by the Phase 4 contract layer. Those technologies can be adapters behind the solver/compiler interfaces later without changing the governance boundary.
