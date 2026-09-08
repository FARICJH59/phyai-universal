from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
from src.phase2_sensors.sensor_adapter import RawSensorSample, SensorAdapter
from src.phase3_simulation.contracts import SimulationAction
from src.phase3_simulation.environments.reference import DeterministicReferenceEnvironment
from src.phase3_simulation.generators.scenarios import ScenarioGenerator
from src.phase4_surrogates.solvers.solver import DeterministicBaselineSolver, SolverRequest
from src.phase5_perception.pipeline import PerceptionPipeline
from src.phase6_control.controller import ControlPipeline
from src.phase7_reasoning.reasoner import ReasoningPipeline
from src.production_hardening.phase16_17_boundary import Phase16To17Boundary
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedExecutionRequest, GovernedHoareClient, TransportAdmission
from src.production_hardening.phase17_evidence import EvidenceVerifier, ExecutionEvidence, HMACSHA256Signer, InMemoryEvidenceStore
from src.production_hardening.phase18_receipt_chain import InMemoryReceiptChainStore, ReceiptChain, ReceiptChainVerifier

REQUIRED_PHASE_MODULES = (
    "src.phase1_contracts.contracts", "src.phase2_sensors.sensor_adapter", "src.phase3_simulation.contracts",
    "src.phase4_surrogates.solvers.solver", "src.phase5_perception.pipeline", "src.phase6_control.controller",
    "src.phase7_reasoning.reasoner", "src.phase8_evaluation.evaluator", "src.production_hardening.learned_world_model",
    "src.production_hardening.learned_multimodal", "src.production_hardening.phase11_onnx",
    "src.production_hardening.phase12_acceleration", "src.production_hardening.phase13_latency",
    "src.production_hardening.phase14_robustness", "src.production_hardening.phase15_hil",
    "src.production_hardening.phase16_hoare_integration", "src.production_hardening.phase17_evidence",
    "src.production_hardening.phase18_receipt_chain",
)


def _command(tenant: str = "tenant-a", project: str = "project-a") -> ControlCommand:
    return ControlCommand(
        tenant_id=tenant, project_id=project, command_id=uuid4(), attempt_id=uuid4(), sequence=1,
        proposed_at=datetime.now(timezone.utc), target_id="device-1", command_type="set_velocity",
        parameters={"velocity": 0.5}, confidence=0.95, safety_precondition_ids=("precondition.safe",),
        scene_id=uuid4(), source_observation_ids=(uuid4(),), provenance_uri="urn:test:command",
    )


class _AdmissionTransport:
    def __init__(self, response: TransportAdmission) -> None:
        self.response = response
        self.requests: list[GovernedExecutionRequest] = []

    def admit(self, request: GovernedExecutionRequest) -> TransportAdmission:
        self.requests.append(request)
        return self.response


def _context(command: ControlCommand) -> dict[str, str]:
    return {"tenant_id": command.tenant_id, "project_id": command.project_id, "policy_digest": "policy-sha256"}


def _transport_admission(command: ControlCommand, artifact_hash: str, context: dict[str, str], **overrides: object) -> TransportAdmission:
    values: dict[str, object] = {
        "accepted": True,
        "attempt_id": command.attempt_id,
        "capability_id": "cap-1",
        "lease_id": "lease-1",
        "fence_id": "fence-1",
        "reason": "accepted",
        "request_digest": GovernedHoareClient.digest_request(command, artifact_hash, context),
    }
    values.update(overrides)
    return TransportAdmission(**values)


def test_all_phases_have_explicit_boundaries() -> None:
    for module_name in REQUIRED_PHASE_MODULES:
        assert import_module(module_name) is not None, module_name


def test_phases_1_to_7_preserve_identity_and_proposal_only_authority() -> None:
    tenant_id, project_id = "tenant-a", "project-a"
    observation = SensorAdapter().ingest(RawSensorSample(
        tenant_id=tenant_id, project_id=project_id, source_id="camera-1", sequence=1,
        sensor_type="rgb", frame_id="frame-1", payload=b"frame", payload_encoding="application/octet-stream",
        calibration_version="cal-v1", provenance_uri="urn:test:sensor", confidence=0.95,
        observed_at=datetime.now(timezone.utc),
    ))
    scenario = ScenarioGenerator().generate(tenant_id, project_id, seed=7)
    environment = DeterministicReferenceEnvironment()
    result = environment.step(environment.reset(scenario), SimulationAction(
        target_id="device-1", command_type="set_velocity", parameters={"velocity": 0.5},
    ))
    assert observation.identity.tenant_id == result.next_state.tenant_id == tenant_id
    assert observation.identity.project_id == result.next_state.project_id == project_id
    assert result.next_state.scenario_id == scenario.scenario_id
    assert not hasattr(SimulationAction, "capability_id")

    solution = DeterministicBaselineSolver().solve(SolverRequest(
        tenant_id=tenant_id, project_id=project_id, scenario_id=scenario.scenario_id,
        objective="reach target", state=result.next_state,
        constraints={"target_position": 0.75, "max_acceleration": 1.0},
    ))
    assert solution.scenario_id == scenario.scenario_id

    scene = PerceptionPipeline().process((observation,)).scene
    command = ControlPipeline().propose(
        scene, target_id="device-1", command_type="set_velocity", parameters={"velocity": 0.5},
        safety_precondition_ids=("precondition.safe",),
    )
    assert scene.tenant_id == command.tenant_id == tenant_id
    assert scene.project_id == command.project_id == project_id
    assert observation.observation_id in command.source_observation_ids
    assert command.scene_id == scene.scene_id
    assert command.is_authorization_free_proposal is True

    reasoning = ReasoningPipeline().reasoning if hasattr(ReasoningPipeline, "reasoning") else ReasoningPipeline().reason
    result = reasoning(scene, objective="maintain stable velocity", target_id="device-1", command_type="set_velocity", safety_precondition_ids=("precondition.safe",), constraints={"max_velocity": 1.0})
    assert result.scene_id == scene.scene_id
    assert result.authorization_required is True


def test_phases_16_to_18_are_strictly_sequential() -> None:
    command = _command()
    context = _context(command)
    artifact_hash = "artifact-sha256"
    response = _transport_admission(command, artifact_hash, context)
    transport = _AdmissionTransport(response)
    client = GovernedHoareClient(transport)
    signer = HMACSHA256Signer("test-key", b"test-secret")
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    boundary = Phase16To17Boundary(client, signer, verifier)

    envelope, signed = boundary.admit_and_sign(command, artifact_hash, context, "policy-sha256")
    assert isinstance(envelope.admission, GovernedAdmission)
    assert signed.identity.capability_id == "cap-1"
    assert signed.identity.lease_id == "lease-1"
    assert signed.identity.fence_id == "fence-1"
    assert transport.requests[0].request_digest == client.digest_request(command, artifact_hash, context)

    evidence = ExecutionEvidence(signed.identity_digest, command.attempt_id, "device-1", 1, 1, "result-sha256", signed.signature)
    receipt = boundary.commit_evidence(envelope, signed, evidence, expected_device_id="device-1")

    chain_store = InMemoryReceiptChainStore()
    entry = ReceiptChain(chain_store).append(receipt)
    verification = ReceiptChainVerifier().verify(chain_store.entries())
    assert verification.valid is True
    assert verification.terminal_digest == entry.chain_digest


def test_fail_closed_on_rebinding_and_unverified_receipt_paths() -> None:
    command = _command()
    context = _context(command)
    artifact_hash = "artifact-sha256"
    digest = GovernedHoareClient.digest_request(command, artifact_hash, context)

    with pytest.raises(ValueError, match="attempt identity"):
        response = _transport_admission(command, artifact_hash, context, attempt_id=uuid4())
        GovernedHoareClient(_AdmissionTransport(response)).admit(command, artifact_hash, context)

    with pytest.raises(PermissionError, match="must originate from verified evidence"):
        from src.production_hardening.phase17_evidence import DurableReceipt
        receipt_digest = DurableReceipt.compute_digest("identity", command.attempt_id, 1, "result")
        DurableReceipt("identity", command.attempt_id, 1, "result", receipt_digest)

    with pytest.raises(ValueError, match="request binding"):
        response = _transport_admission(command, artifact_hash, context, request_digest="wrong")
        GovernedHoareClient(_AdmissionTransport(response)).admit(command, artifact_hash, context)

    assert digest == GovernedHoareClient.digest_request(command, artifact_hash, context)
