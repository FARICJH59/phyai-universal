# Phase 2 — Sensors

Phase 2 establishes the hardware-neutral sensor boundary.

```text
Physical driver
    ↓
SensorAdapter
    ↓
RawSensorSample
    ↓
SensorNormalizer
    ↓
SensorObservation (Phase 1)
    ↓
Tokenizer / Fusion
    ↓
Perception
```

## Invariants

1. Physical drivers do not define domain contracts.
2. Every observation carries tenant, project, source, sequence, timestamp, calibration, confidence, and provenance.
3. Observations from different tenants or projects cannot be fused.
4. Sensor payload bytes remain opaque to the normalization layer.
5. Tokenization is deterministic and operates on canonical observation metadata.
6. No sensor component can authorize or directly actuate a physical side effect.

Phase 2 intentionally stops before perception. Phase 3 simulation and later phases consume these contracts rather than bypassing them.
