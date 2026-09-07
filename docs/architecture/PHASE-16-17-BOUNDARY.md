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
GovernedAdmission
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
