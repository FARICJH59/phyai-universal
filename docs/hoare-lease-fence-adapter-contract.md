# HOARE Lease/Fence Adapter Contract

**Record date:** 2026-10-31  
**Record time:** 01:25:19 UTC  
**Repository:** FARICJH59/phyai-universal  
**Classification:** PUBLIC INTERFACE CONTRACT — implementation-neutral

## Purpose

Define the minimum public interface PHyAI needs to verify that a previously admitted execution still holds a current, unrevoked lease and fencing generation immediately before physical dispatch.

This document does not describe or reproduce HOARE's proprietary lease, capability, AEGIS, or fencing implementation.

## Authority boundary

- HOARE remains the sole authority for admission, lease state, revocation, and current fencing generation.
- PHyAI is a relying party. It verifies signed status and enforces a fail-closed dispatch boundary.
- PHyAI must not mint, renew, extend, revoke, or independently infer HOARE leases.
- A successful lookup is a point-in-time authorization check, not a physical-safety determination.
- A production transport must authenticate the HOARE service and protect the channel (for example, mutually authenticated TLS), apply strict timeouts, and fail closed on transport errors.

## Request contract: hoare.lease-fence.v1

The relying party sends:

- tenant_id
- project_id
- device_id
- capability_id
- lease_id
- fence_id
- cryptographically unpredictable one-time nonce (minimum 256 bits)
- requested_at (Unix seconds)
- contract_version

The service must bind its response to every identity field and echo the exact nonce.

## Signed response contract

The service returns an Ed25519-signed response containing:

- authority_id
- tenant_id, project_id, device_id
- capability_id, lease_id, fence_id
- current_fence_id
- lease_expires_at
- revoked
- request_nonce
- issued_at
- response_expires_at
- key_id
- algorithm = Ed25519
- contract_version = hoare.lease-fence.v1
- signature over canonical JSON (UTF-8, sorted keys, compact separators, ASCII escaping), excluding the signature field

The response is valid only if:
1. key_id resolves to a provisioned trusted HOARE public key;
2. signature verifies;
3. all requested identities match exactly;
4. request_nonce matches the outstanding request and has not been reused;
5. contract version is supported;
6. issued_at and response_expires_at satisfy the relying party's freshness limits;
7. lease is not revoked or expired; and
8. current_fence_id equals the admitted fence_id.

Unknown keys, malformed responses, stale responses, mismatches, timeout, network failure, or verification errors MUST fail closed.

## Key management

- HOARE private signing keys remain exclusively within HOARE-controlled infrastructure or approved hardware-backed key custody.
- PHyAI receives public verification keys through an authenticated, separately governed provisioning channel.
- Key rotation must support explicit key IDs and an overlap period.
- Test signing helpers and test keys are not production credentials.

## Implementation status

PHyAI now contains a verifier/adapter wrapper and contract tests. It intentionally does not invent a HOARE URL, HTTP route, token format, or proprietary implementation. A deployment-specific transport remains to be implemented only after HOARE publishes or approves the endpoint, authentication, timeout, and response mapping contract.

This adapter is not approved for live physical actuation until that transport is implemented, independently reviewed, and tested against the authoritative HOARE service.
