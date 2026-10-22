# HOARE Robotics Integration and IP Boundary

**Document date:** 2026-10-22  
**Repository:** `FARICJH59/phyai-universal`  
**Status:** Public integration guidance; not a certification or safety case.

## Purpose

Define a reusable, target-agnostic integration boundary for physical-AI workloads. PHyAI-Universal models observations, scenes, and proposed actions. A proposed action is not execution permission. A connected HOARE deployment must independently authorize any governed side effect through its configured trusted control plane before a robot or actuator receives an actionable command.

This document describes an integration contract, not a claim that every listed adapter already exists or has been tested.

## Supported integration families

Each family is a target for a separately implemented and tested adapter:

- **Robot middleware:** ROS 2, DDS-based systems, and vendor middleware.
- **Edge compute:** NVIDIA Jetson-class systems, Raspberry Pi-class systems, x86 edge gateways, and industrial PCs.
- **Manipulators:** industrial arms, collaborative robots, grippers, and end effectors.
- **Mobile robotics:** AMRs, AGVs, warehouse robots, and field robots.
- **Aerial systems:** UAVs and other unmanned aerial platforms.
- **Autonomous platforms:** ground vehicles and other mobile autonomous systems, subject to applicable safety and regulatory requirements.
- **Embodied AI:** vision-language-action and learned-policy systems, with model output treated as a proposal rather than authority.
- **Simulation and validation:** digital twins, simulators, hardware-in-the-loop (HIL), software-in-the-loop (SIL), and shadow-mode evaluation.
- **Industrial and physical systems:** sensors, PLC-adjacent gateways, energy systems, and other controlled equipment where the target's safety and regulatory requirements permit integration.

A family appearing in this list is not evidence of vendor compatibility, functional safety certification, or production readiness.

## Canonical data path

```text
Sensors / model outputs
        |
        v
PHyAI domain contracts
(observation -> scene -> action proposal)
        |
        v
HOARE trusted authorization boundary
(allow / deny / escalate; deployment-specific)
        |
        v
Target adapter verifies authorization bound to the exact proposal
        |
        v
Independent target safety controls -> simulated or physical actuation attempt
        |
        v
Observed result + traceable evidence -> verification / reconciliation
```

### Authorization and adapter boundary

The authorization decision must be delivered to the trusted target adapter through the deployment's approved interface; it must not be relayed as an unverified string or boolean from PHyAI. Before any actuation attempt, the adapter must verify that the authorization is valid and bound to the exact command/attempt, tenant, project, target, permitted scope, and freshness window. It must also apply replay protection and confirm that authority has not expired or been revoked through the configured trusted mechanism.

This repository does not define a production HOARE authorization wire format, signature scheme, lease protocol, or revocation transport. Those must be specified against the actual HOARE/AEGIS implementation and reviewed before integration. A mock verifier in a simulation is test scaffolding, not cryptographic verification or proof of production authorization.

### Boundary rules

1. Keep domain data separate from credentials, authorization grants, leases, fencing tokens, and execution authority.
2. Treat every control command as a proposal until the trusted authorization boundary approves the exact action, target, scope, and freshness requirements.
3. Do not infer permission from an HTTP success, a model response, a status string, a hash, a queue acknowledgement, or the presence of a command.
4. Bind an actuation attempt to tenant/project identity, target identity, unique attempt identity, relevant observation/scene lineage, freshness/deadline, and a verifiable authorization result.
5. Denial, timeout, expired/revoked authority, malformed responses, signature-verification failure, stale state, or unavailable authorization must not trigger actuation. Surface an explicit failure/escalation result.
6. Use idempotency and replay protection where supported. Reconcile uncertain outcomes rather than blindly retrying a physical action.
7. Maintain an independent, target-appropriate safety controller, emergency-stop path, and operator override. Software authorization is not a substitute for physical safety mechanisms.
8. Validate the complete path in simulation first, then shadow mode, then bounded controlled trials with documented operator approval. Never enable live actuation merely because a contract test passes.
9. Record evidence sufficient to correlate proposal, authorization decision, attempted command, target response, and post-action observation. Protect sensitive logs and credentials.
10. Measure end-to-end latency at the relevant boundary. A local handler timer is not proof of control-loop latency or deterministic performance.

## Adapter conformance gate

Before an adapter can be considered for a target, its tests and deployment review should cover:

- schema validation, units, coordinate frames, timestamp normalization, confidence bounds, and source lineage;
- target and tenant/project binding, freshness, deadline, and duplicate-attempt behavior;
- deny, escalate, timeout, revocation, stale-state, malformed-response, and verifier-failure cases;
- authentication, least privilege, secret handling, replay resistance, and audit/evidence integrity;
- rate limits, backpressure, reconnects, partial failures, and uncertain actuation outcomes;
- physical limits and target-specific safety interlocks, tested with the robot vendor's documented procedures;
- simulation/shadow/controlled rollout gates and an independently tested stop/rollback procedure;
- reproducible test results and a named human owner for production enablement.

No adapter should claim conformance until the applicable tests pass on the relevant version and target. Contract tests alone do not establish functional safety or certification.

## Intellectual-property and disclosure boundary

This repository is public. Keep only intentionally public domain contracts, generic adapter interfaces, and non-sensitive conformance guidance here.

Do **not** publish or commit:

- proprietary HOARE-CORE or AEGIS source, internal decision logic, private policy schemas, authorization/lease/fencing implementations, private keys, credentials, or signing material;
- customer data, private telemetry, production traces, sensitive benchmark inputs, confidential deployment diagrams, or customer-specific workflows;
- unpublished invention details that have not been cleared for public disclosure.

Recommended engineering controls:

- Keep proprietary implementation in access-controlled private repositories and private build/release systems.
- Use least-privilege repository and cloud access; require review for public releases and external contributions.
- Keep secrets out of source, fixtures, container layers, logs, and build artifacts; rotate any credential suspected of exposure.
- Maintain dated invention records, contributor/inventor records, change history, and an inventory of third-party and open-source licenses.
- Use appropriate confidentiality, invention-assignment, and contractor agreements where applicable; mark and restrict confidential materials.
- Review public commits, package contents, container images, and documentation for sensitive material before release.
- Ask qualified IP counsel to evaluate patentability, ownership, prior art, filing strategy, and disclosure timing before publishing potentially patentable details.

These measures are operational guidance, not a representation that a patent, trademark, copyright registration, or trade-secret right has been filed, granted, or established. Do not use “patent pending” unless a qualifying patent application has actually been filed. A U.S. provisional application generally requires a sufficiently detailed written description and any necessary drawings, identifies all inventors, and must be followed by an appropriate nonprovisional filing within 12 months to claim its benefit. Public disclosure can affect rights, particularly outside the United States; obtain advice from a registered patent practitioner.

## Implementation status

This document establishes a public integration boundary only. The separate simulated gripper demonstration is explicitly a mock-admission, simulation-only research harness. Neither this document nor that harness adds robot drivers, connects a live robot, validates production HOARE authorization, authorizes physical actuation, or certifies safety. Each adapter and deployment remains a separate implementation and verification task.
