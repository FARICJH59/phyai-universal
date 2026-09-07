from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase2_sensors.sensor_adapter import RawSensorSample, SensorAdapter
from src.phase3_simulation.generators.scenarios import ScenarioGenerator
from src.phase4_surrogates.solvers.solver import DeterministicBaselineSolver, SolverRequest
from src.phase5_perception.pipeline import PerceptionPipeline
from src.phase6_control.controller import ControlPipeline
from src.phase7_reasoning.reasoner import ReasoningPipeline
from src.phase8_evaluation.evaluator import DeterministicEvaluator
from src.production_hardening.learned_multimodal import (
    EncodedMultimodalFusion,
    LearnedMultimodalRepresentation,
    TensorModalityInput,
)
from src.production_hardening.learned_world_model import (
    EncodedLearnedWorldModelAdapter,
    LearnedWorldModelRequest,
    TensorWorldModelInput,
    VideoFrame,
    action_feature_encoder,
)
from src.production_hardening.multimodal import ModalityInput
from src.production_hardening.phase11_onnx import compare_outputs
from src.production_hardening.phase12_acceleration import (
    CudaExecutionResult,
    TensorRTExecutionAdapter,
    TensorRTExecutionResult,
    TimedCudaKernel,
)
from src.production_hardening.phase13_latency import EndToEndLatencyHarness
from src.production_hardening.phase14_robustness import SimToRealRobustnessHarness
from src.production_hardening.phase15_hil import (
    ActuationRequest,
    ExecutionEvidence as HardwareExecutionEvidence,
    HardwareInLoopBoundary,
)
from src.production_hardening.phase16_17_boundary import Phase16To17Boundary
from src.production_hardening.phase16_hoare_integration import (
    GovernedAdmission,
    GovernedExecutionRequest,
    GovernedHoareClient,
)
from src.production_hardening.phase17_evidence import (
    EvidenceVerifier,
    ExecutionEvidence,
    HMACSHA256Signer,
    InMemoryEvidenceStore,
)
from src.production_hardening.phase18_receipt_chain import (
    InMemoryReceiptChainStore,
    ReceiptChain,
    ReceiptChainVerifier,
)
from src.production_hardening.world_model import ActionCondition

ROOT = __file__.split("tests/integration/")[0]
TENANT = "tenant-sequential"
PROJECT = "project-sequential"
ARTIFACT_HASH = "artifact-sha256-1"
POLICY_DIGEST = "policy-sha256-1"
DEVICE = "device-1"


def _observation():
    return SensorAdapter().ingest(
        RawSensorSample(
            TENANT,
            PROJECT,
            "camera-1",
            1,
            "rgb",
            "frame-1",
            b"rgb",
            "raw",
            "cal-v1",
            "urn:test:observation",
            0.98,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )


def _scene():
    return PerceptionPipeline().process((_observation(),)).scene


def _command():
    scene = _scene()
    return ControlPipeline().propose(
        scene,
        target_id=DEVICE,
        command_type="position",
        parameters={"position": 0.5},
        safety_precondition_ids=("safe-envelope",),
        attempt_id=uuid4(),
    )


def test_all_phase_boundaries_exist():
    expected = [
        "src/phase1_contracts",
        "src/phase2_sensors",
        "src/phase3_simulation",
        "src/phase4_surrogates",
        "src/phase5_perception",
        "src/phase6_control",
        "src/phase7_reasoning",
        "src/phase8_evaluation",
        "src/production_hardening/learned_world_model.py",
        "src/production_hardening/learned_multimodal.py",
        "src/production_hardening/phase11_onnx.py",
        "src/production_hardening/phase12_acceleration.py",
        "src/production_hardening/phase13_latency.py",
        "src/production_hardening/phase14_robustness.py",
        "src/production_hardening/phase15_hil.py",
        "src/production_hardening/phase16_hoare_integration.py",
        "src/production_hardening/phase17_evidence.py",
        "src/production_hardening/phase18_receipt_chain.py",
    ]
    assert all((__import__("pathlib").Path(ROOT) / path).exists() for path in expected)


def test_runtime_spine_preserves_identity_and_authority_order():
    observation = _observation()
    scene = _scene()
    assert scene.tenant_id == TENANT and scene.project_id == PROJECT
    assert observation.observation_id in scene.source_observation_ids

    reasoning = ReasoningPipeline().reason(
        scene,
        objective="track target",
        target_id=DEVICE,
        command_type="position",
        safety_precondition_ids=("safe-envelope",),
        constraints={"target_position": 0.8, "max_acceleration": 1.0},
    )
    assert reasoning.scene_id == scene.scene_id
    assert reasoning.authorization_required

    simulation = ScenarioGenerator().generate(TENANT, PROJECT, 7)
    solution = DeterministicBaselineSolver().solve(
        SolverRequest(
            TENANT,
            PROJECT,
            simulation.scenario_id,
            "track target",
            simulation,
            {"target_position": 0.8, "max_acceleration": 1.0},
        )
    )
    assert solution.scenario_id == simulation.scenario_id

    action = ActionCondition(
        reasoning.plan.command_type,
        {"acceleration": float(solution.values["acceleration"])},
    )
    request = LearnedWorldModelRequest(
        TENANT,
        PROJECT,
        scene.scene_id,
        (VideoFrame(1, b"frame"),),
        (action,),
        2,
    )

    class Encoder:
        def encode_frames(self, frames):
            return ((1.0,),)

        def encode_actions(self, actions, horizon):
            return action_feature_encoder(actions, horizon)

    class LearnedModel:
        model_id = "test-model"

        def predict(self, model_input: TensorWorldModelInput):
            return ((0.1,), (0.2,))

    rollout = EncodedLearnedWorldModelAdapter(LearnedModel(), Encoder()).predict(request)
    assert (rollout.tenant_id, rollout.project_id, rollout.scene_id) == (
        TENANT,
        PROJECT,
        scene.scene_id,
    )

    modalities = (
        ModalityInput("rgb", b"rgb", "raw", 10, 0.95),
        ModalityInput("proprioception", b"joint", "raw", 11, 0.97),
    )

    class ModalityEncoder:
        def __init__(self, name):
            self.name = name

        def encode(self, modality):
            return TensorModalityInput(
                self.name,
                (float(modality.timestamp_ns),),
                modality.timestamp_ns,
                modality.confidence,
            )

    class Fusion:
        encoder_id = "fusion-test"

        def fuse(self, tenant_id, project_id, inputs):
            return LearnedMultimodalRepresentation(
                tenant_id,
                project_id,
                max(x.timestamp_ns for x in inputs),
                tuple(x.modality for x in inputs),
                tuple(v for x in inputs for v in x.features),
                min(x.confidence for x in inputs),
                self.encoder_id,
            )

    representation = EncodedMultimodalFusion(
        {"rgb": ModalityEncoder("rgb"), "proprioception": ModalityEncoder("proprioception")},
        Fusion(),
    ).fuse(TENANT, PROJECT, modalities)
    assert representation.modality_order == ("rgb", "proprioception")

    command = ControlPipeline().propose(
        scene,
        target_id=reasoning.plan.target_id,
        command_type=reasoning.plan.command_type,
        parameters=reasoning.plan.parameters,
        safety_precondition_ids=tuple(reasoning.plan.safety_precondition_ids),
    )
    assert command.is_authorization_free_proposal
    assert command.source_observation_ids == tuple(scene.source_observation_ids)

    evaluation = DeterministicEvaluator().evaluate(
        scene,
        command,
        {key: float(value) for key, value in command.parameters.items()},
    )
    assert evaluation.passed

    assert compare_outputs((0.1, 0.2), (0.1, 0.20001), tolerance=1e-3).samples == 2

    class TrtRunner:
        def infer(self, inputs):
            return TensorRTExecutionResult("engine-test", (sum(inputs),), 1.5)

    class CudaRunner:
        def run(self, inputs):
            return CudaExecutionResult("kernel-test", (sum(inputs),), 0.5)

    assert TensorRTExecutionAdapter(TrtRunner(), "engine-test").infer((1.0, 2.0)).engine_id == "engine-test"
    assert TimedCudaKernel(CudaRunner(), "kernel-test").run((1.0, 2.0)).kernel_id == "kernel-test"

    assert EndToEndLatencyHarness(50.0).measure(lambda: rollout.frames, iterations=3).passed
    assert SimToRealRobustnessHarness().evaluate(
        "rgb", (1.0, 2.0), (1.01, 1.99), ((0.0, 0.1),), ((0.01, 0.1),), 0.95
    ).passed

    class Actuator:
        def apply(self, request):
            return HardwareExecutionEvidence(
                request.attempt_id, request.device_id, 1, "result-1", True
            )

    admission = GovernedAdmission(True, command.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")

    class GovernanceTransport:
        def admit(self, request: GovernedExecutionRequest):
            assert request.command.command_id == command.command_id
            assert request.artifact_hash == ARTIFACT_HASH
            return admission

    signer = HMACSHA256Signer("test-key", b"test-secret")
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    boundary = Phase16To17Boundary(
        GovernedHoareClient(GovernanceTransport()), signer, verifier
    )
    envelope, signed = boundary.admit_and_sign(
        command,
        ARTIFACT_HASH,
        {"tenant_id": TENANT, "project_id": PROJECT},
        POLICY_DIGEST,
    )
    assert signed.identity.capability_id == admission.capability_id
    assert signed.identity.lease_id == admission.lease_id
    assert signed.identity.fence_id == admission.fence_id

    # Phase 15 physical execution accepts authority only from the Phase 16 result.
    authority_hil = HardwareInLoopBoundary(Actuator())
    hardware_request = ActuationRequest(
        TENANT,
        PROJECT,
        DEVICE,
        str(command.attempt_id),
        GovernedHoareClient.digest_request(command, ARTIFACT_HASH),
        {"x": 0.1},
    )
    hardware_evidence = authority_hil.execute(hardware_request, admission)
    assert hardware_evidence.attempt_id == str(command.attempt_id)

    evidence = ExecutionEvidence(
        signed.identity_digest,
        command.attempt_id,
        DEVICE,
        1,
        1000,
        hardware_evidence.result_digest,
        signed.signature,
    )
    receipt = boundary.commit_evidence(
        envelope,
        signed,
        evidence,
        expected_device_id=DEVICE,
    )

    chain_store = InMemoryReceiptChainStore()
    entry = ReceiptChain(chain_store).append(
        identity_digest=receipt.identity_digest,
        attempt_id=receipt.attempt_id,
        sequence=receipt.sequence,
        result_digest=receipt.result_digest,
    )
    verification = ReceiptChainVerifier().verify(chain_store.entries())
    assert verification.valid and verification.terminal_digest == entry.chain_digest


def test_denied_admission_stops_before_phase_17_and_physical_execution():
    command = _command()

    class DenyingTransport:
        def admit(self, request):
            return GovernedAdmission(False, request.command.attempt_id, None, None, None, "denied")

    signer = HMACSHA256Signer("key", b"secret")
    boundary = Phase16To17Boundary(
        GovernedHoareClient(DenyingTransport()),
        signer,
        EvidenceVerifier(InMemoryEvidenceStore()),
    )
    with pytest.raises(PermissionError, match="denied admission"):
        boundary.admit_and_sign(
            command,
            ARTIFACT_HASH,
            {"tenant_id": TENANT, "project_id": PROJECT},
            POLICY_DIGEST,
        )

    class Actuator:
        def apply(self, request):
            raise AssertionError("denied authority must never reach actuator")

    class DeniedAuthority:
        accepted = False
        attempt_id = command.attempt_id
        capability_id = None
        lease_id = None
        fence_id = None

    with pytest.raises(PermissionError):
        HardwareInLoopBoundary(Actuator()).execute(
            ActuationRequest(TENANT, PROJECT, DEVICE, str(command.attempt_id), "digest", {"x": 0.1}),
            DeniedAuthority(),
        )


def test_phase_16_request_digest_binds_execution_identity():
    command = _command()
    first = GovernedHoareClient.digest_request(command, ARTIFACT_HASH)
    second = GovernedHoareClient.digest_request(command, ARTIFACT_HASH)
    changed_artifact = GovernedHoareClient.digest_request(command, "artifact-sha256-2")
    assert first == second
    assert first != changed_artifact


def test_phase_18_rejects_identity_rebinding():
    store = InMemoryReceiptChainStore()
    chain = ReceiptChain(store)
    attempt = uuid4()
    first = chain.append(
        identity_digest="identity-a",
        attempt_id=attempt,
        sequence=1,
        result_digest="result-a",
    )
    from src.production_hardening.phase18_receipt_chain import ReceiptChainEntry

    forged = ReceiptChainEntry(
        identity_digest="identity-b",
        attempt_id=attempt,
        sequence=2,
        result_digest="result-b",
        previous_receipt_digest=first.chain_digest,
        chain_digest=ReceiptChainEntry.compute_digest(
            "identity-b", attempt, 2, "result-b", first.chain_digest
        ),
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        store.append(forged)
