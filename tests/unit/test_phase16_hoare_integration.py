from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase16_hoare_integration import (
    GovernedAdmission,
    GovernedHoareClient,
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


def test_admission_requires_authority_returned_by_hoare():
    cmd = command()
    admission = GovernedAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")
    transport = FakeTransport(admission)
    result = GovernedHoareClient(transport).admit(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"})
    assert result.accepted
    assert transport.requests[0].request_digest == GovernedHoareClient.digest_request(cmd, "artifact")


def test_denial_carries_no_authority():
    cmd = command()
    admission = GovernedAdmission(False, cmd.attempt_id, None, None, None, "denied")
    assert not GovernedHoareClient(FakeTransport(admission)).admit(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"}).accepted


def test_cross_tenant_fails_before_transport():
    cmd = command()
    transport = FakeTransport(GovernedAdmission(False, cmd.attempt_id, None, None, None, "denied"))
    with pytest.raises(PermissionError, match="tenant mismatch"):
        GovernedHoareClient(transport).admit(cmd, "artifact", {"tenant_id": "other", "project_id": "project-a"})
    assert not transport.requests


def test_attempt_identity_cannot_be_rebound():
    cmd = command()
    admission = GovernedAdmission(True, uuid4(), "cap-1", "lease-1", "fence-1", "admitted")
    with pytest.raises(ValueError, match="attempt identity"):
        GovernedHoareClient(FakeTransport(admission)).admit(cmd, "artifact", {"tenant_id": "tenant-a", "project_id": "project-a"})


def test_denied_admission_cannot_include_authority():
    cmd = command()
    with pytest.raises(ValueError, match="denied admission"):
        GovernedAdmission(False, cmd.attempt_id, "cap-1", None, None, "denied")
