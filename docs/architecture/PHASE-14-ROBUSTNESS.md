# Phase 14 — Sim-to-Real and Noisy-Sensor Robustness

Phase 14 establishes a deterministic robustness evaluation boundary for perturbing modality features and measuring downstream output and trajectory degradation.

## Evaluation

For each modality perturbation:

`baseline input → baseline output/trajectory`

`perturbed input → perturbed output/trajectory`

The harness computes relative output change, mean trajectory deviation, and confidence. A result fails closed when confidence is below the configured safety threshold or either degradation threshold is exceeded.

Supported modality names are intentionally open-ended, including RGB, depth, proprioception, tactile, and language. The harness does not claim that these inputs came from physical sensors.

## Evidence boundary

This phase provides reusable robustness contracts and controlled perturbation evaluation. It does **not** establish physical sim-to-real transfer by itself.

Not yet claimed:

- physical sensor capture;
- camera/depth hardware characterization;
- tactile hardware characterization;
- real robot calibration drift;
- hardware-in-the-loop validation;
- domain-randomized learned-model training;
- demonstrated sim-to-real success rate.

Physical validation belongs in the next hardware-in-the-loop phase.

## Safety boundary

Robustness evaluation can reject a proposed downstream result, but it cannot authorize physical execution. Execution authority remains with HOARE and its AEGIS/TCX governance boundary.
