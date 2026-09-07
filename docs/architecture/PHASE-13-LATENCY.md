# Phase 13 — End-to-End Latency Instrumentation

Phase 13 measures the complete injected software pipeline as one transaction and uses p95 latency as the pass/fail criterion.

## Measurement boundary

`input → multimodal representation → learned inference → trajectory/control proposal`

Callers provide the pipeline callable. The harness measures wall-clock elapsed time around the entire callable rather than timing isolated model operations.

## Report

Each report contains:

- individual latency samples;
- arithmetic mean;
- p95 latency;
- maximum latency;
- configured target;
- pass/fail based on p95 ≤ target.

The default target is 50 ms, matching the Jetson target configuration. A target passing in CI is only a software-harness result and is not evidence of Jetson, TensorRT, CUDA, or physical-loop performance.

## Evidence boundary

Not yet claimed:

- sub-50-ms physical control loop;
- GPU latency;
- TensorRT latency;
- CUDA latency;
- Jetson latency;
- sensor I/O latency;
- actuator latency;
- hardware-in-the-loop timing.

Those require measurements on the actual deployment stack.
