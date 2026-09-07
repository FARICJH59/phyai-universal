# Phase 6 — Control

Phase 6 transforms a validated `SpatialScene` into a `ControlCommand` proposal. It does not dispatch commands or grant authority.

```text
SpatialScene
    |
    v
SafetyValidator
    |
    +---- reject on failed preconditions/confidence
    |
    v
ProposalController
    |
    v
ControlCommand (proposal only)
    |
    v
HOARE / AEGIS / TCX
```

## Safety boundary

The reference safety gate requires a minimum scene confidence of `0.90`, non-empty parameters, and numeric parameter values. Failed validation is fail-closed. This is intentionally a local pre-command gate, not a replacement for HOARE authorization or AEGIS admission.

## Authority boundary

`ControlCommand` is explicitly authorization-free. Phase 6 creates no capability, lease, fence, authorization, dispatch, or actuation object. Execution authority remains outside PHyAI-Universal and must be established by the HOARE control plane.

## Lineage

A proposal preserves the scene's tenant, project, scene ID, sequence, and source observation IDs. The proposal receives a fresh attempt/command identity so later execution evidence can bind to a distinct attempt without changing the originating scene.
