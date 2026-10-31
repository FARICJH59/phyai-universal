from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.phase1_contracts.contracts import ControlCommand
from src.production_hardening.phase15_hil import (
    ActuationRequest,
    ExecutionEvidence,
    HardwareInLoopBoundary,
    HardwareObservation,
    validate_sensor_sequence,
)
from src.production_hardening.admission_proof import (
    AdmissionClaims, Ed25519AdmissionProofVerifier, sign_admission_claims,
)
from src.production_hardening.phase16_hoare_integration import GovernedHoareClient, TransportAdmission



_TEST_PRIVATE_KEY = Ed25519PrivateKey.generate()
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
_TEST_NOW = 1_800_000_000
_TEST_VERIFIER = Ed25519AdmissionProofVerifier(
    {"test-hoare-key": _TEST_PUBLIC_KEY}, clock=lambda: _TEST_NOW
)


def signed_proof(cmd):
    digest = GovernedHoareClient.digest_request(cmd, "artifact", context())
    claims = AdmissionClaims(
        authority_id="hoare-test", tenant_id=cmd.tenant_id, project_id=cmd.project_id,
        device_id=cmd.target_id, attempt_id=str(cmd.attempt_id), request_digest=digest,
        capability_id="cap-1", lease_id="lease-1", fence_id="fence-1",
        key_id="test-hoare-key", issued_at=_TEST_NOW - 1, expires_at=_TEST_NOW + 30,
    )
    return sign_admission_claims(claims, _TEST_PRIVATE_KEY)


def execute_with_proof(actuator, req, authority, original_command):
    return HardwareInLoopBoundary(actuator, _TEST_VERIFIER).execute(
        req, authority, signed_proof(original_command)
    )


class FakeTransport:
    def __init__(self, admission):
        self.admission = admission

    def admit(self, request):
        return self.admission


def command():
    return ControlCommand(
        tenant_id="tenant", project_id="project", command_id=uuid4(), attempt_id=uuid4(),
        sequence=1, proposed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        target_id="robot-1", command_type="position", parameters={"velocity": 1.0}, confidence=0.95,
        safety_precondition_ids=("safe-1",), scene_id=uuid4(), source_observation_ids=(uuid4(),),
        provenance_uri="urn:test", schema_version="v1",
    )


def context():
    return {"tenant_id": "tenant", "project_id": "project", "policy_digest": "policy-1"}


def governed_authority(cmd):
    digest = GovernedHoareClient.digest_request(cmd, "artifact", context())
    response = TransportAdmission(True, cmd.attempt_id, "cap-1", "lease-1", "fence-1", "admitted", digest)
    return GovernedHoareClient(FakeTransport(response)).admit(cmd, "artifact", context())


class Actuator:
    def __init__(self, verified=True):
        self.verified = verified
        self.calls = 0

    def apply(self, request):
        self.calls += 1
        return ExecutionEvidence(request.attempt_id, request.device_id, 1, "digest", self.verified)


def request(cmd):
    ctx = context()
    digest = GovernedHoareClient.digest_request(cmd, "artifact", ctx)
    return ActuationRequest(cmd.tenant_id, cmd.project_id, cmd.target_id, str(cmd.attempt_id), digest, dict(cmd.parameters), cmd, "artifact", ctx)


def test_hil_rejects_fabricated_structural_authority():
    actuator = Actuator()
    fabricated = type("Authority", (), {
        "accepted": True, "attempt_id": "attempt", "capability_id": "cap-1",
        "lease_id": "lease-1", "fence_id": "fence-1",
    })()
    cmd = command()
    req = request(cmd)
    with pytest.raises(PermissionError, match="requires Phase 16"):
        HardwareInLoopBoundary(actuator, _TEST_VERIFIER).execute(req, fabricated, signed_proof(cmd))
    assert actuator.calls == 0


def test_hil_accepts_only_phase16_governed_admission():
    cmd = command()
    actuator = Actuator()
    evidence = execute_with_proof(actuator, request(cmd), governed_authority(cmd), cmd)
    assert evidence.verified
    assert evidence.attempt_id == str(cmd.attempt_id)
    assert actuator.calls == 1


def test_hil_rejects_denied_phase16_admission():
    cmd = command()
    denied = TransportAdmission(False, cmd.attempt_id, None, None, None, "denied")
    authority = GovernedHoareClient(FakeTransport(denied)).admit(cmd, "artifact", context())
    actuator = Actuator()
    with pytest.raises(PermissionError, match="admission denied"):
        execute_with_proof(actuator, request(cmd), authority, cmd)
    assert actuator.calls == 0


def test_hil_binds_attempt_to_governed_authority():
    cmd = command()
    actuator = Actuator()
    req = request(cmd)
    # Simulate hostile mutation bypassing the frozen dataclass API.
    object.__setattr__(req, "attempt_id", str(uuid4()))
    with pytest.raises(ValueError, match="attempt identity"):
        execute_with_proof(actuator, req, governed_authority(cmd), cmd)
    assert actuator.calls == 0


def test_hil_rejects_unverified_evidence():
    cmd = command()
    with pytest.raises(RuntimeError, match="evidence failed verification"):
        execute_with_proof(Actuator(False), request(cmd), governed_authority(cmd), cmd)


def test_sensor_sequence_preserves_tenant_project_and_order():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (1.0,)),
        HardwareObservation("tenant", "project", "robot-1", 1, 20, (2.0,)),
    ]
    validate_sensor_sequence(observations)


def test_sensor_sequence_rejects_cross_tenant():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (1.0,)),
        HardwareObservation("other", "project", "robot-1", 1, 20, (2.0,)),
    ]
    with pytest.raises(ValueError, match="cross-tenant"):
        validate_sensor_sequence(observations)


def test_sensor_sequence_rejects_replay_or_reordering():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 1, 10, (1.0,)),
        HardwareObservation("tenant", "project", "robot-1", 1, 20, (2.0,)),
    ]
    with pytest.raises(ValueError, match="sequence must increase"):
        validate_sensor_sequence(observations)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_hardware_observation_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="finite"):
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (value,))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True])
def test_actuation_request_rejects_non_finite_or_boolean_parameters(value):
    cmd = command()
    ctx = context()
    digest = GovernedHoareClient.digest_request(cmd, "artifact", ctx)
    with pytest.raises(ValueError, match="finite"):
        ActuationRequest(
            cmd.tenant_id, cmd.project_id, cmd.target_id, str(cmd.attempt_id),
            digest, {"velocity": value}, cmd, "artifact", ctx
        )


def test_sensor_sequence_rejects_timestamp_regression():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 0, 20, (1.0,)),
        HardwareObservation("tenant", "project", "robot-1", 1, 10, (2.0,)),
    ]
    with pytest.raises(ValueError, match="timestamp must increase"):
        validate_sensor_sequence(observations)


def test_sensor_sequence_rejects_device_identity_change():
    observations = [
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (1.0,)),
        HardwareObservation("tenant", "project", "robot-2", 1, 20, (2.0,)),
    ]
    with pytest.raises(ValueError, match="device identity changed"):
        validate_sensor_sequence(observations)


def test_execution_evidence_rejects_invalid_verified_type():
    with pytest.raises(ValueError, match="verified must be a boolean"):
        ExecutionEvidence("attempt", "robot-1", 1, "digest", 1)


def test_observation_rejects_integer_too_large_for_finite_float():
    with pytest.raises(ValueError, match="finite"):
        HardwareObservation("tenant", "project", "robot-1", 0, 10, (10 ** 10000,))


@pytest.mark.parametrize("field,value", [
    ("target_id", "robot-2"),
    ("command_type", "emergency_stop"),
    ("parameters", {"velocity": 9.0}),
    ("confidence", 0.1),
    ("sequence", 99),
])
def test_hil_rejects_actuation_request_rebound_to_altered_command(field, value):
    from dataclasses import replace
    cmd = command()
    altered = replace(cmd, **{field: value})
    authority = governed_authority(cmd)
    original = request(cmd)
    actuator = Actuator()
    if field == "target_id":
        # A target mismatch is rejected while constructing the request.
        with pytest.raises(ValueError, match="target"):
            ActuationRequest(
                original.tenant_id, original.project_id, original.device_id, original.attempt_id,
                GovernedHoareClient.digest_request(altered, "artifact", context()),
                dict(altered.parameters), altered, "artifact", context()
            )
    else:
        rebound = ActuationRequest(
            original.tenant_id, original.project_id, original.device_id, original.attempt_id,
            GovernedHoareClient.digest_request(altered, "artifact", context()),
            dict(altered.parameters), altered, "artifact", context()
        )
        with pytest.raises(PermissionError, match="does not bind"):
            execute_with_proof(actuator, rebound, authority, cmd)
    assert actuator.calls == 0


def test_hil_rechecks_mutable_command_parameters_immediately_before_actuator():
    cmd = command()
    authority = governed_authority(cmd)
    req = request(cmd)
    cmd.parameters["velocity"] = 999.0
    actuator = Actuator()
    with pytest.raises(ValueError, match="parameters do not match"):
        execute_with_proof(actuator, req, authority, cmd)
    assert actuator.calls == 0


def test_hil_rejects_wrong_artifact_or_policy_context_binding():
    cmd = command()
    authority = governed_authority(cmd)
    req = request(cmd)
    altered_context = {**context(), "policy_digest": "different-policy"}
    altered_digest = GovernedHoareClient.digest_request(cmd, "different-artifact", altered_context)
    rebound = ActuationRequest(
        req.tenant_id, req.project_id, req.device_id, req.attempt_id,
        altered_digest, dict(cmd.parameters), cmd, "different-artifact", altered_context
    )
    actuator = Actuator()
    with pytest.raises(PermissionError, match="does not bind"):
        execute_with_proof(actuator, rebound, authority, cmd)
    assert actuator.calls == 0
