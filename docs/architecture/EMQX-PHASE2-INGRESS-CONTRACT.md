# EMQX-to-PHyAI Phase 2 Ingress Contract

**Status:** Architecture contract proposal; implementation not yet started  
**Date:** 2026-10-30  
**Timestamp:** 2026-10-30T23:02:30-04:00  
**Target:** `FARICJH59/phyai-universal`  
**Branch:** `feat/emqx-phase2-ingress-contract-20261030`

## 1. Purpose

Define a broker-neutral boundary for receiving MQTT telemetry from EMQX and adapting validated messages into the existing PHyAI Phase 2 sensor contract.

This document does not add a second MQTT broker/client framework, change the Phase 1 observation contract, implement a live EMQX connection, or authorize physical actions.

## 2. Existing PHyAI boundary to preserve

The current Phase 2 flow is:

```text
Physical driver / transport adapter
    -> RawSensorSample
    -> SensorAdapter
    -> SensorNormalizer
    -> SensorObservation (Phase 1)
    -> Tokenizer / Fusion
    -> Perception
```

The existing `RawSensorSample` fields are the integration target:

- `tenant_id`
- `project_id`
- `source_id`
- `sequence`
- `sensor_type`
- `frame_id`
- `payload`
- `payload_encoding`
- `calibration_version`
- `provenance_uri`
- `confidence`
- `observed_at`

The MQTT adapter must construct this existing type and call `SensorAdapter.ingest()`. It must not implement another normalizer or fusion engine.

## 3. Logical responsibilities

### EMQX / MQTT transport

- Authenticate MQTT clients using broker-supported credentials and, where deployed, mutual TLS.
- Enforce publish/subscribe authorization with broker ACLs.
- Deliver MQTT messages and transport metadata.
- Apply broker-level connection, session, QoS and message-size policies.

### PHyAI MQTT ingress adapter

- Decode the transport envelope and validate its schema/version.
- Resolve the authenticated MQTT principal to a registered device identity.
- Resolve that device identity to its authorized tenant, project and source identifiers.
- Verify that the requested topic is permitted for that principal and registered source.
- Validate required metadata and payload bounds before constructing `RawSensorSample`.
- Preserve the original payload bytes and source provenance.
- Call the existing Phase 2 `SensorAdapter`.
- Return or record a typed ingress outcome; never turn a telemetry message into an actuator command.

### Phase 2

- Remains responsible for canonical sensor normalization.
- Remains responsible for observation contracts and fusion.
- Does not depend on EMQX-specific types or APIs.

### Phase 19 / Phase 20

- Phase 19 consumes eligible, validated observations through a separate dataset-selection and provenance process.
- Phase 20 consumes versioned datasets/model artifacts for local learning and evaluation.
- Neither phase subscribes directly to broker topics as a substitute for the PHyAI ingress boundary.

### HOARE / AEGIS / TCX

- Retain independent authority for governed admission, execution and deployment.
- MQTT connectivity, message delivery, model training and model evaluation do not grant execution authority.

## 4. Topic convention proposal

Proposed versioned topic shape:

```text
phyai/v1/tenants/{tenant_id}/projects/{project_id}/devices/{device_id}/sensors/{sensor_id}/observations
```

Rules:

1. Topic segments are routing identifiers, not proof of identity.
2. The authenticated MQTT principal must be mapped through a trusted device registry.
3. The tenant/project/device/sensor values in the topic must match that registry mapping; mismatches are rejected.
4. Device principals receive the minimum publish rights needed for their registered topic subtree.
5. Device principals do not receive wildcard access to other tenants or projects.
6. Command/control topics are outside this telemetry ingress contract and require a separate design.

## 5. Message envelope proposal

The transport envelope should carry, at minimum:

- envelope/schema version;
- event/message identifier;
- source sequence number;
- sensor type and frame identifier;
- observed-at timestamp with explicit UTC offset or UTC representation;
- payload encoding/content type;
- calibration version;
- confidence, when meaningful and validated;
- payload bytes or an explicitly encoded payload;
- provenance/reference metadata.

Tenant, project and source identity must be resolved from authenticated device registration. Values supplied by the payload alone must not override that trusted mapping.

The existing `proto/v1/sensor_stream.proto` remains the canonical PHyAI observation schema. An MQTT JSON or Protobuf envelope may be used at the transport boundary, but it must map losslessly to the existing observation fields or be rejected. Any schema evolution to the canonical protobuf is a separate reviewed change.

## 6. Delivery, ordering and idempotency

- Start with QoS 1 for telemetry where delivery acknowledgement is required; make QoS configurable per registered device/topic policy.
- Do not claim QoS 1 or QoS 2 guarantees exactly-once application processing.
- Deduplicate at the PHyAI ingress/application boundary using a stable event identity and/or the registered source identity plus sequence number, with a documented retention window.
- Detect duplicate, stale and out-of-order messages. The initial policy should reject or quarantine ambiguous sequence regressions rather than silently reorder them.
- Preserve broker receive time separately from device observed time if both are available.
- Reject timestamps without timezone information; apply explicit clock-skew limits as a configurable device policy.
- Do not enable retained messages for high-rate telemetry by default. Retained state/configuration messages need a separate contract.
- Define bounded retry and dead-letter/quarantine behavior before production deployment.

## 7. Validation and security requirements

Ingress must fail closed when any of the following is missing or invalid:

- authenticated principal / registered device mapping;
- tenant/project/source authorization;
- permitted topic and sensor identity mapping;
- supported schema version and payload encoding;
- required sequence and timestamp fields;
- payload size and structural limits;
- calibration metadata required for the sensor type;
- provenance requirements.

Additional controls:

- TLS certificate verification must remain enabled.
- Credentials and private keys must not be logged or committed.
- Broker ACLs and PHyAI authorization checks are complementary; neither replaces the other.
- Validate all numeric values for finiteness and permitted ranges before they enter downstream contracts.
- Record rejection reasons without exposing secrets or cross-tenant data.
- A valid MQTT message is data, not authorization to execute a physical action.

## 8. Error/outcome contract

The adapter should expose a small typed result vocabulary, for example:

- `ACCEPTED`: converted to a canonical Phase 2 observation.
- `DUPLICATE`: already processed under the configured idempotency policy.
- `REJECTED_AUTH`: principal, device, tenant, project or topic authorization failed.
- `REJECTED_SCHEMA`: envelope or payload schema is invalid/unsupported.
- `REJECTED_METADATA`: sequence, timestamp, calibration or provenance is invalid.
- `REJECTED_LIMIT`: payload or rate limits exceeded.
- `QUARANTINED`: validly received but requires operator/data-quality review.

The exact Python types and persistence behavior are implementation decisions for the next step.

## 9. Non-goals

This contract does not:

- replace `lib/mqtt.ts` in `tech-fusion-grid-ui`;
- claim that the existing UI MQTT client is a production EMQX deployment;
- turn the HOARE-AGENT connector readiness check into a working broker consumer;
- create a new PHyAI sensor normalization/fusion engine;
- implement an MQTT command channel or physical actuator interface;
- implement dataset storage/training (Phase 19/20);
- establish real-time or safety certification claims.

## 10. Acceptance criteria for the first implementation slice

1. A broker-neutral ingress contract can be unit-tested without a live broker.
2. An authenticated device identity maps to exactly one authorized tenant/project/source scope.
3. Topic claims cannot override trusted device registration.
4. A valid message maps to the existing `RawSensorSample` and is normalized only by `SensorAdapter`.
5. Invalid identity, topic, schema, timestamp, sequence and payload size fail closed.
6. Duplicate delivery is idempotent under the documented key/window.
7. Tests prove that telemetry cannot invoke actuator or HOARE execution APIs.
8. No changes are made to Phase 15–18 work or existing open pull requests.

## 11. Implementation sequence

- **EMQX-1 (this document):** agree and record the boundary contract.
- **EMQX-2:** add broker-neutral envelope, identity-resolution and ingress result types; no network client yet.
- **EMQX-3:** implement mapping into the existing `RawSensorSample` / `SensorAdapter`.
- **EMQX-4:** add validation, idempotency and quarantine tests.
- **EMQX-5:** add an optional EMQX integration test profile using a disposable broker; keep default CI broker-independent.

A live EMQX deployment, production credentials, device registry, broker ACLs and physical hardware tests remain separate verification requirements.
