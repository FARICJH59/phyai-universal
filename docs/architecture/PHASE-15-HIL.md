# Phase 15 — Hardware-in-the-Loop and Governed Physical Execution

Phase 15 introduces the physical I/O boundary without pretending that CI is a physical testbed.

## Control path

`physical sensor → HardwareObservation → perception/reasoning → control proposal → Phase 16 HOARE admission → governed authority → ActuationRequest → physical actuator → ExecutionEvidence → Phase 17 verification`

The Phase 15 adapter requires an explicit governed authority proof before calling the actuator. The proof must be accepted, must bind to the request attempt, and must contain capability, lease, and fence identifiers. A denied or incomplete authority proof fails closed before the actuator is called.

## Identity and replay controls

Hardware observations carry tenant, project, device, sequence, and timestamp identity. A sensor sequence validator rejects cross-tenant/project observations and non-increasing sequence numbers.

Actuation requests carry tenant, project, device, attempt, command digest, and parameters. Phase 15 does not mint attempts, capabilities, leases, fences, or authorization. Authority remains a Phase 16 HOARE/AEGIS/TCX responsibility and is passed into this boundary as an explicit proof.

## Sequential boundary

The intended runtime dependency is:

```text
Phase 6 control proposal
        ↓
Phase 16 governed admission
        ↓
Phase 15 physical/HIL execution
        ↓
Phase 17 cryptographic evidence verification
        ↓
Phase 18 receipt chain
```

Phase numbers describe implementation progression; this diagram describes the authority dependency. Physical execution is not permitted merely because a physical adapter exists.

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
