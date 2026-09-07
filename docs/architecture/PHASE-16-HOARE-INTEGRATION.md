# Phase 16 — HOARE / AEGIS / TCX Integration Boundary

Phase 16 replaces the Phase 15 boolean-style admission abstraction with a governed request/response contract suitable for a real HOARE deployment.

## Boundary

`ControlCommand → GovernedHoareClient → HoareGovernanceTransport → HOARE/AEGIS/TCX → GovernedAdmission`

PHyAI creates a deterministic request digest from the command execution identity and artifact hash. It does not create capability, lease, or fence authority.

An accepted response must contain:

- the original attempt identity;
- capability identity;
- lease identity;
- fence identity;
- an admission reason.

A denied response cannot contain execution authority.

## Security invariants

1. Tenant and project mismatches fail before transport invocation.
2. Admission cannot be rebound to another attempt.
3. Authority identifiers are transport outputs, never locally minted.
4. The artifact hash participates in the request digest.
5. PHyAI remains proposal-producing; HOARE remains execution-governing.

## Deployment evidence

The repository now contains the integration contract and deterministic tests. A configured production transport, cryptographic identity, live AEGIS policy evaluation, TCX admission, capability leasing, fencing, and physical execution are still required before claiming a live HOARE integration.

This distinction is intentional: interface readiness is not deployment evidence.
