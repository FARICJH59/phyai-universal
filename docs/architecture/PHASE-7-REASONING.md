# Phase 7 — Reasoning

Phase 7 turns a `SpatialScene` into a bounded plan. Reasoning can optimize, plan, explain, and propose; it cannot authorize or execute physical effects.

```text
SpatialScene
    |
    v
ReasoningRequest
    |
    v
Planner / ReasoningAgent
    |
    v
Plan
    |
    +--> authorization_required = true
    |
    v
Phase 6 / HOARE boundary
```

## Interfaces

- `Planner` is the framework-neutral planning contract.
- `ReasoningAgent` is the agentic adapter boundary.
- `DeterministicPlanner` provides a reproducible reference implementation for contract tests.
- Production LLM, VLM, classical planner, optimization solver, or hybrid agent implementations can replace the reference planner without changing the domain contracts.

## Authority invariants

- A plan is not an executable command.
- Reasoning does not create leases, capabilities, fences, dispatch records, or actuation requests.
- Safety preconditions are required inputs to planning.
- Scene identity is preserved so downstream governance can bind a proposal to its evidence.
- The final physical side effect remains governed by HOARE, AEGIS, and TCX.
