# Phase 5 — Perception

Phase 5 converts canonical `SensorObservation` records into canonical `SpatialScene` records.

## Boundary

```text
SensorObservation
      |
      v
ObservationFusion
      |
      v
VGGT-compatible predictor interface
      |
      +---- optional spatial acceleration (CUDA or other backend)
      |
      v
SpatialScene
```

The perception layer may reconstruct, estimate, and describe the physical scene. It does **not** authorize, lease, fence, dispatch, or actuate anything.

## VGGT boundary

`VGGTPredictor` is a model interface. `ReferenceVGGTPredictor` exists only for deterministic contract testing and does not claim to perform trained VGGT inference. A production deployment can provide a real VGGT implementation without changing the Phase 1 contracts or the pipeline boundary.

## CUDA boundary

`SpatialAcceleration` is an optional optimization interface. The portable identity implementation preserves representation bytes exactly, allowing contract tests and non-CUDA deployments to remain independent of GPU libraries. CUDA implementations must preserve the semantic contract rather than introduce authority.

## Invariants

- Tenant and project isolation is enforced before perception.
- Observation IDs are preserved as scene lineage.
- Scene confidence is conservatively bounded by the least-confident input observation.
- Scene identity is deterministic for the same tenant, project, sequence, and ordered source IDs.
- Raw sensor payloads remain opaque at the contract boundary; the reference backend records content hashes rather than interpreting payload bytes.
- No capability, lease, authorization, fence, or actuation field is produced by perception.
- `ControlCommand` remains downstream and proposal-only until HOARE governance.
