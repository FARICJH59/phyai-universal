# Phase 8 — Evaluation and Data Flywheel

Phase 8 closes the initial PHyAI workload loop with deterministic evaluation, failure classification, criticism, and curated evaluation records.

```text
Scene + Control Proposal
          |
          v
    EvaluationCase
          |
          v
 DeterministicEvaluator
          |
     +----+----+
     |         |
 metrics    failure modes
     |         |
     +----+----+
          |
          v
       Critic
          |
          v
  EvaluationRecord
          |
          v
    Data Flywheel
```

## Invariants

- Evaluation is isolated by tenant and project.
- Scene identity must match the proposal being evaluated.
- Missing expected parameters fail evaluation rather than being inferred.
- Quantitative evaluation is deterministic and bounded.
- Failure modes are explicit and machine-readable.
- Curated records retain tenant/project identity and evaluation results.
- Evaluation never authorizes, dispatches, or actuates a physical command.
- Future VLM critics and training-data pipelines must remain behind these boundaries.

This phase establishes the evaluation/data boundary; it does not claim that a production VLM judge or model-training service has been deployed.
