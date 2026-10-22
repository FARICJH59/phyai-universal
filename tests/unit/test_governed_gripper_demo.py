from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts.contracts import ControlCommand
from src.phase1_contracts.harness.governed_gripper_demo import (
    GovernedGripperDemo,
    MockAuthorizationResult,
    SimulatedGripper,
    proposal_digest,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def make_command(*, proposed_at=NOW, attempt_id=None, target_id="sim-gripper-1", position=20.0):
    return ControlCommand(
        "tenant-a",
        "project-a",
        uuid4(),
        attempt_id or uuid4(),
        1,
        proposed_at,
        target_id,
        "set_gripper_position_mm",
        {"position_mm": position},
        0.95,
        ["simulation-workspace-clear"],
        uuid4(),
        [uuid4()],
        "evidence://simulation/scene-1",
    )


def make_authorization(command, **overrides):
    values = {
        "decision": "ALLOW",
        "tenant_id": command.tenant_id,
        "project_id": command.project_id,
        "command_id": command.command_id,
        "attempt_id": command.attempt_id,
        "target_id": command.target_id,
        "command_type": command.command_type,
        "action_digest": proposal_digest(command),
        "issued_at": NOW - timedelta(milliseconds=1),
        "expires_at": NOW + timedelta(seconds=1),
    }
    values.update(overrides)
    return MockAuthorizationResult(**values)


def make_demo(command, authorization_factory=None, *, verifier=None, now=NOW):
    gripper = SimulatedGripper()
    def provider(proposal):
        if authorization_factory:
            return authorization_factory(proposal)
        return make_authorization(proposal)
    demo = GovernedGripperDemo(
        gripper,
        provider,
        verifier or (lambda result: result.proof == b"simulation-only"),
        now=lambda: now,
    )
    return demo, gripper


def test_allow_performs_only_bounded_simulated_actuation():
    command = make_command()
    demo, gripper = make_demo(command)
    result = demo.execute(command)

    assert result.status == "ALLOW"
    assert result.actuation_attempted is True
    assert gripper.position_mm == 20.0
    assert gripper.attempts == [20.0]
    assert any(event["event"] == "simulated_actuation" for event in result.evidence)
    assert result.elapsed_ns >= 0


@pytest.mark.parametrize("decision", ["DENY", "ESCALATE"])
def test_non_allow_decision_never_actuates(decision):
    command = make_command()
    demo, gripper = make_demo(
        command, lambda proposal: make_authorization(proposal, decision=decision)
    )

    result = demo.execute(command)

    assert result.status == "DENY"
    assert result.actuation_attempted is False
    assert gripper.attempts == []


def test_authorization_timeout_fails_closed():
    command = make_command()
    def timeout(_proposal):
        raise TimeoutError("mock admission timeout")
    demo, gripper = make_demo(command, timeout)

    result = demo.execute(command)

    assert result.reason == "authorization_unavailable"
    assert result.actuation_attempted is False
    assert gripper.attempts == []


def test_stale_proposal_fails_before_authorization():
    command = make_command(proposed_at=NOW - timedelta(seconds=5))
    called = False
    def provider(_proposal):
        nonlocal called
        called = True
        return make_authorization(command)
    demo, gripper = make_demo(command, provider)

    result = demo.execute(command)

    assert result.reason == "stale_or_future_proposal"
    assert called is False
    assert gripper.attempts == []


def test_replayed_attempt_is_rejected():
    command = make_command()
    demo, gripper = make_demo(command)

    first = demo.execute(command)
    second = demo.execute(command)

    assert first.actuation_attempted is True
    assert second.reason == "replayed_attempt"
    assert second.actuation_attempted is False
    assert gripper.attempts == [20.0]


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("target_id", "other-gripper"),
        ("command_type", "different-action"),
        ("tenant_id", "other-tenant"),
        ("project_id", "other-project"),
        ("command_id", uuid4()),
        ("attempt_id", uuid4()),
    ],
)
def test_authorization_binding_mismatch_never_actuates(field, wrong_value):
    command = make_command()
    demo, gripper = make_demo(
        command,
        lambda proposal: make_authorization(proposal, **{field: wrong_value}),
    )

    result = demo.execute(command)

    assert result.reason == "authorization_binding_mismatch"
    assert gripper.attempts == []


def test_authorization_with_different_action_digest_is_rejected():
    command = make_command()
    demo, gripper = make_demo(
        command,
        lambda proposal: make_authorization(proposal, action_digest="0" * 64),
    )

    result = demo.execute(command)

    assert result.reason == "authorization_binding_mismatch"
    assert gripper.attempts == []


def test_revoked_authorization_is_rejected():
    command = make_command()
    demo, gripper = make_demo(
        command, lambda proposal: make_authorization(proposal, revoked=True)
    )

    result = demo.execute(command)

    assert result.reason == "authorization_revoked"
    assert gripper.attempts == []


def test_expired_authorization_is_rejected():
    command = make_command()
    demo, gripper = make_demo(
        command,
        lambda proposal: make_authorization(
            proposal, expires_at=NOW - timedelta(milliseconds=1)
        ),
    )

    result = demo.execute(command)

    assert result.reason == "authorization_expired_or_invalid_window"
    assert gripper.attempts == []


def test_verifier_failure_is_rejected():
    command = make_command()
    demo, gripper = make_demo(command, verifier=lambda _result: False)

    result = demo.execute(command)

    assert result.reason == "authorization_verification_failed"
    assert gripper.attempts == []


def test_verifier_exception_fails_closed():
    command = make_command()
    def broken_verifier(_result):
        raise RuntimeError("mock verifier failure")
    demo, gripper = make_demo(command, verifier=broken_verifier)

    result = demo.execute(command)

    assert result.reason == "authorization_verification_failed"
    assert gripper.attempts == []


def test_malformed_authorization_result_fails_closed():
    command = make_command()
    demo, gripper = make_demo(command, lambda _proposal: None)

    result = demo.execute(command)

    assert result.reason == "malformed_authorization_result"
    assert gripper.attempts == []


def test_proposal_mutation_after_admission_fails_closed():
    command = make_command()

    def mutate_after_authorization(proposal):
        authorization = make_authorization(proposal)
        proposal.parameters["position_mm"] = 10.0
        return authorization

    demo, gripper = make_demo(command, mutate_after_authorization)
    result = demo.execute(command)

    assert result.reason == "proposal_changed_after_authorization"
    assert result.actuation_attempted is False
    assert gripper.attempts == []


def test_out_of_bounds_target_command_is_not_actuated():
    command = make_command(position=100.0)
    demo, gripper = make_demo(command)

    result = demo.execute(command)

    assert result.reason == "target_rejected_command"
    assert result.actuation_attempted is False
    assert gripper.attempts == []
