# Phase 15 — Hardware-in-the-Loop and Governed Physical Execution

Phase 15 introduces the physical I/O boundary without pretending that CI is a physical testbed.

## Control path

`physical sensor → HardwareObservation → perception/reasoning → control proposal → HOARE admission → ActuationRequest → physical actuator → ExecutionEvidence → verification`

The adapter requires an explicit admission decision before calling the actuator. A denied decision fails closed. Evidence must preserve the attempt and device identity and must be verified before the boundary returns success.

## Identity and replay controls

Hardware observations carry tenant, project, device, sequence, and timestamp identity. A sensor sequence validator rejects cross-tenant/project observations and non-increasing sequence numbers.

Actuation requests carry tenant, project, device, attempt, command digest, and parameters. This phase does not mint attempts, capabilities, leases, fences, or authorization; those remain HOARE responsibilities.

## Test status boundary

The Phase 15 CI suite validates the software contract with injected test doubles. It does **not** establish that a robot, Jetson, actuator, camera, depth sensor, tactile sensor, or HIL rig has been exercised.

Physical evidence still required:

- real sensor capture;
- calibrated device identity;
- real actuator command path;
- measured end-to-end latency;
- fault injection and recovery;
- hardware-in-the-loop traces;
- durable execution receipts from the real HOARE integration.

Only after those artifacts exist should production claims about physical execution or sim-to-real performance be made.
