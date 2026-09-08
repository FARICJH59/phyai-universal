# Phase 16 → 17 Boundary

This document defines the mandatory sequential handoff from governed admission to cryptographic execution identity and evidence.

## Sequence

```text
ControlCommand
    ↓
Phase 16: GovernedHoareClient
    ↓
HOARE / AEGIS / TCX transport
    ↓
GovernedAdmission (request_digest bound)
    ↓
Phase16AdmissionEnvelope
    ↓
ExecutionIdentity.from_governed_admission()
    ↓
SignedAdmissionArtifact
    ↓
Physical / HIL execution
    ↓
ExecutionEvidence
    ↓
EvidenceVerifier.commit_verified_evidence()
    ↓
DurableReceipt
    ↓
Phase 18 receipt chain
```

## Admission request binding

The Phase 16 request digest canonically binds the complete security-relevant execution request, including:

- tenant and project identity;
- command and attempt identity;
- sequence and proposal timestamp;
- target and command type;
- command parameters;
- confidence and safety preconditions;
- scene and source-observation lineage;
- provenance URI and schema version;
- artifact hash;
- complete policy/security context.

An accepted `GovernedAdmission` must carry the exact request digest returned for the request. A transport response with a mismatched or missing binding is rejected before authority crosses the Phase 16 boundary.

## Boundary invariants

- A denied Phase 16 admission cannot enter Phase 17.
- The admission attempt ID must equal the proposed command attempt ID.
- Capability, lease, and fence identifiers must originate from the accepted Phase 16 admission.
- The artifact hash and policy digest used for Phase 17 must remain bound to the Phase 16 handoff.
- The signed identity must be derived from the governed admission rather than independently inventing authority identifiers.
- Evidence must be verified against the signed admission before a receipt is committed.
- Device identity, attempt identity, admission signature, and execution identity must remain bound.
- The handoff is fail closed on artifact, policy, identity, or authority drift.

## Non-goals

This boundary does not claim a live production HOARE/AEGIS/TCX transport, production HSM/KMS, or physical hardware deployment. It establishes the contract-level sequencing required before those integrations are introduced.
