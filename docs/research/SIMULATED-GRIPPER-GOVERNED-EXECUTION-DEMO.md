# Simulation-Only Governed Gripper Research Demo

**Created:** 2026-10-22 UTC  
**Scope:** PHyAI contract objects + injected mock admission + in-memory gripper target.  
**Safety boundary:** No robot driver, ROS/DDS connection, physical I/O, production HOARE endpoint, or cryptographic authorization verifier is present.

## Research question

Can a target adapter demonstrate that it only attempts a bounded simulated action after receiving a valid, fresh, action-bound allow result—and that denial, timeout, stale proposals, replay, revocation, invalid binding, verifier failure, and target-limit violations fail closed?

## Run

From the repository root with the test extra installed:

```bash
python -m pip install -e '.[test]'
python -m pytest -q tests/unit/test_governed_gripper_demo.py tests/unit/test_phase1_contracts.py
```

The test suite is the intended first gate. Run the repository's complete test suite before treating this demo as integrated with the wider project.

## Scenario

The simulated gripper begins at 80 mm and receives a proposed move to 20 mm. The adapter accepts only the target `sim-gripper-1`, command type `set_gripper_position_mm`, and a numeric position within 0–80 mm. It uses the existing `ControlCommand` contract, whose authorization-free proposal semantics remain unchanged.

The authorization provider and verifier are injected test doubles. The verifier in these tests checks a clearly labeled simulation marker only; it does not validate a signature, credential, lease, fence, or live HOARE/AEGIS decision. The harness therefore tests adapter behavior around a mock decision, not HOARE itself.

## Required scenarios and expected outcome

| Scenario | Expected behavior |
|---|---|
| Valid, fresh, exact-bound ALLOW | One in-memory actuation attempt |
| DENY or ESCALATE | No actuation |
| Authorization provider timeout/exception | Fail closed; no actuation |
| Stale or future proposal | Reject before contacting admission |
| Repeated attempt ID | Reject duplicate; do not actuate again |
| Authorization bound to another target or action | Reject |
| Revoked or expired authorization | Reject |
| Verifier returns false or raises | Reject |
| Target command outside simulation limits | Reject |

The suite also records an in-process elapsed-time measurement and decision/actuation evidence identifiers. This timing is only a local harness measurement; it is not a latency benchmark, a p95/p99 result, a deterministic timing guarantee, or a robot control-loop measurement.

## Research protocol after the tests pass

1. Capture the commit SHA, Python version, dependency lock/environment, command line, test output, and UTC timestamp.
2. Run repeated simulation batches and report count, success/failure counts, and latency distributions (median, p95, p99); distinguish admission time from total harness time.
3. Add deterministic fault injection for provider timeout, invalid binding, stale state, duplicate attempts, and uncertain target outcomes. Preserve every failing seed/input.
4. Review evidence completeness: proposal ID, attempt ID, target, decision/reason, simulated action, and result must correlate without exposing credentials.
5. Compare against a baseline simulator without admission overhead, while holding task, machine, and workload constant.
6. Do not progress to HIL until the mock is replaced by an approved interface to the actual HOARE/AEGIS trusted boundary, the authorization artifact is bound to the exact attempt and target, revocation/replay behavior is verified, and a robotics safety owner approves the test plan.
7. Any HIL experiment must use documented vendor procedures, independent safety interlocks, an emergency stop, bounded operating conditions, and explicit human authorization. Passing these unit tests is not permission for physical actuation.

## Acceptance criteria

- The unit suite passes reproducibly.
- Every negative authorization/freshness/replay scenario records zero simulated actuation attempts.
- A valid allow scenario records exactly one bounded simulated attempt.
- Test output and environment provenance are retained.
- No result is described as live HOARE integration, production cryptographic verification, functional-safety certification, or real-robot validation.
