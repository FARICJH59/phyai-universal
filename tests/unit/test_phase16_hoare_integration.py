from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import (
    GovernedAdmission,
    GovernedHoareClient,
    TransportAdmission,
)


class FakeTransport:
    def __init__(self, admission):
        self.admission = admission
        self.requests = []

    def admit(self, request):
        self.requests.append(request)
        return self.admission


def command():
    return ControlCommand(
        tenant_id="tenant-a", project_id="project-a", command_id=uuid4(), attempt_id=uuid4(),
        sequence=1, proposed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        target_id="arm-1", command_type="position", parameters={"x": 0.1}, confidence=0.95,
        safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )


def context():
    return {"tenant_id": "tenant-a", "project_id": "project-a", "policy_digest": "policy-1"}


def transport_admission(cmd, artifact="artifact", ctx=None, **overrides):
    ctx = ctx or context()
    values = {
        "accepted": True,
        "attempt_id": cmd.attempt_id,
        "capability_id": "cap-1",
        "lease_id": "lease-1",
        "fence_id": "fence-1",
        "reason": "admitted",
        "request_digest": GovernedHoareClient.digest_request(cmd, artifact, ctx),
    }
    values.update(overrides)
    return TransportAdmission(**values)


def test_admission_requires_authority_returned_by_hoare():
    cmd = command()
    ctx = context()
    transport = FakeTransport(transport_admission(cmd, ctx=ctx))
    result = GovernedHoareClient(transport).admit(cmd, "artifact", ctx)
    assert isinstance(result, GovernedAdmission)
    assert result.accepted
    assert transport.requests[0].request_digest == GovernedHoareClient.digest_request(cmd, "artifact", ctx)


def test_local_governed_admission_constructor_is_sealed():
    cmd = command()
    with pytest.raises(PermissionError, match="only originate from HOARE transport"):
        GovernedAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted", "digest")


def test_accepted_admission_with_wrong_request_binding_fails_closed():
    cmd = command()
    ctx = context()
    admission = transport_admission(cmd, ctx=ctx, request_digest="wrong-digest")
    with pytest.raises(ValueError, match="request binding"):
        GovernedHoareClient(FakeTransport(admission)).admit(cmd, "artifact", ctx)


def test_denial_carries_no_authority():
    cmd = command()
    denied = TransportAdmission(False, cmd.attempt_id, None, None, None, "denied")
    assert not GovernedHoareClient(FakeTransport(denied)).admit(cmd, "artifact", context()).accepted


def test_cross_tenant_fails_before_transport():
    cmd = command()
    transport = FakeTransport(TransportAdmission(False, cmd.attempt_id, None, None, None, "denied"))
    with pytest.raises(PermissionError, match="tenant mismatch"):
        GovernedHoareClient(transport).admit(cmd, "artifact", {"tenant_id": "other", "project_id": "project-a"})
    assert not transport.requests


def test_attempt_identity_cannot_be_rebound():
    cmd = command()
    ctx = context()
    admission = transport_admission(cmd, ctx=ctx, attempt_id=uuid4())
    with pytest.raises(ValueError, match="attempt identity"):
        GovernedHoareClient(FakeTransport(admission)).admit(cmd, "artifact", ctx)


def test_denied_transport_response_cannot_include_authority():
    cmd = command()
    denied = TransportAdmission(False, cmd.attempt_id, "cap-1", None, None, "denied")
    with pytest.raises(ValueError, match="denied admission"):
        GovernedHoareClient(FakeTransport(denied)).admit(cmd, "artifact", context())


def test_request_digest_changes_with_security_relevant_context():
    cmd = command()
    ctx = context()
    baseline = GovernedHoareClient.digest_request(cmd, "artifact", ctx)
    changed_parameters = cmd.__class__(
        tenant_id=cmd.tenant_id, project_id=cmd.project_id, command_id=cmd.command_id, attempt_id=cmd.attempt_id,
        sequence=cmd.sequence, proposed_at=cmd.proposed_at, target_id=cmd.target_id, command_type=cmd.command_type,
        parameters={"x": 0.2}, confidence=cmd.confidence, safety_precondition_ids=cmd.safety_precondition_ids,
        scene_id=cmd.scene_id, source_observation_ids=cmd.source_observation_ids, provenance_uri=cmd.provenance_uri,
        schema_version=cmd.schema_version,
    )
    changed_context = {**ctx, "policy_digest": "policy-2"}
    assert baseline != GovernedHoareClient.digest_request(changed_parameters, "artifact", ctx)
    assert baseline != GovernedHoareClient.digest_request(cmd, "artifact", changed_context)
