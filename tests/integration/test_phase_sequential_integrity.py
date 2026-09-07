from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ControlCommand
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
    TensorRTExecutionResult,
    TensorRTExecutionAdapter,
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
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedHoareClient
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


TENANT = "tenant-sequential"
PROJECT = "project-sequential"
ARTIFACT_HASH = "artifact-sha256-1"
POLICY_DIGEST = "policy-sha256-1"


def test_phase_1_to_18_preserves_identity_and_authority_order() -> None:
    # Phase 1 -> 2: raw sensor data becomes the canonical observation contract.
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observation = SensorAdapter().ingest(
        RawSensorSample(
            tenant_id=TENANT,
            project_id=PROJECT,
            source_id="camera-1",
            sequence=1,
            sensor_type="rgb",
            frame_id="frame-1",
            payload=b"rgb-frame",
            payload_encoding="raw",
            calibration_version="cal-v1",
            provenance_uri="urn:test:sensor:1",
            confidence=0.98,
            observed_at=observed_at,
        )
    )
    assert observation.identity.tenant_id == TENANT
    assert observation.identity.project_id == PROJECT
    assert observation.identity.sequence == 1

    # Phase 3 -> 4: simulation and surrogate requests preserve tenant/project/scenario.
    simulation = ScenarioGenerator().generate(TENANT, PROJECT, seed=7)
    solution = DeterministicBaselineSolver().solve(
        SolverRequest(
            tenant_id=TENANT,
            project_id=PROJECT,
            scenario_id=simulation.scenario_id,
            objective="track target",
            state=simulation,
            constraints={"target_position": 0.8, "max_acceleration": 1.0},
        )
    )
    assert solution.scenario_id == simulation.scenario_id

    # Phase 5 -> 6: observations become a spatial scene, then a proposal-only command.
    scene = PerceptionPipeline().process((observation,)).scene
    assert scene.tenant_id == TENANT
    assert scene.project_id == PROJECT
    assert observation.observation_id in scene.source_observation_ids

    command = ControlPipeline().propose(
        scene,
        target_id="arm-1",
        command_type="position",
        parameters={"x": float(solution.values["acceleration"])},
        safety_precondition_ids=("precondition-safe",),
    )
    assert command.is_authorization_free_proposal
    assert command.tenant_id == TENANT
    assert command.project_id == PROJECT
    assert command.scene_id == scene.scene_id
    assert command.source_observation_ids == tuple(scene.source_observation_ids)

    # Phase 7 -> 8: reasoning remains a plan and evaluation remains non-authorizing.
    reasoning = ReasoningPipeline().reason(
        scene,
        objective="track target",
        target_id=command.target_id,
        command_type=command.command_type,
        safety_precondition_ids=tuple(command.safety_precondition_ids),
        constraints={"target_position": 0.8, "max_acceleration": 1.0},
    )
    assert reasoning.scene_id == scene.scene_id
    assert reasoning.authorization_required is True
    evaluation = DeterministicEvaluator().evaluate(scene, command, {"x": command.parameters["x"]})
    assert evaluation.passed

    # Phase 9: action-conditioned learned-world-model boundary is explicit.
    action = ActionCondition(command.command_type, {"acceleration": float(command.parameters["x"])})
    world_request = LearnedWorldModelRequest(
        tenant_id=TENANT,
        project_id=PROJECT,
        scene_id=scene.scene_id,
        frames=(VideoFrame(1, b"frame"),),
        actions=(action,),
        horizon=2,
    )

    class Encoder:
        def encode_frames(self, frames):
            return ((1.0,),)

        def encode_actions(self, actions, horizon):
            return action_feature_encoder(actions, horizon)

    class LearnedModel:
        model_id = "test-learned-model"

        def predict(self, model_input: TensorWorldModelInput):
            assert len(model_input.action_features) == model_input.horizon
            return ((0.1,), (0.2,))

    rollout = EncodedLearnedWorldModelAdapter(LearnedModel(), Encoder()).predict(world_request)
    assert rollout.tenant_id == TENANT
    assert rollout.project_id == PROJECT
    assert rollout.scene_id == scene.scene_id
    assert len(rollout.frames) == 2

    # Phase 10: learned multimodal representation preserves modality order and identity.
    modalities = (
        ModalityInput("rgb", b"rgb", "raw", 10, 0.95),
        ModalityInput("proprioception", b"joint", "raw", 11, 0.97),
    )

    class ModalityEncoderImpl:
        def __init__(self, name):
            self.name = name

        def encode(self, modality):
            return TensorModalityInput(self.name, (float(modality.timestamp_ns),), modality.timestamp_ns, modality.confidence)

    class FusionImpl:
        encoder_id = "test-fusion"

        def fuse(self, tenant_id, project_id, inputs):
            return LearnedMultimodalRepresentation(
                tenant_id,
                project_id,
                max(item.timestamp_ns for item in inputs),
                tuple(item.modality for item in inputs),
                tuple(value for item in inputs for value in item.features),
                min(item.confidence for item in inputs),
                self.encoder_id,
            )

    representation = EncodedMultimodalFusion(
        {"rgb": ModalityEncoderImpl("rgb"), "proprioception": ModalityEncoderImpl("proprioception")},
        FusionImpl(),
    ).fuse(TENANT, PROJECT, modalities)
    assert representation.tenant_id == TENANT
    assert representation.project_id == PROJECT
    assert representation.modality_order == ("rgb", "proprioception")

    # Phase 11 -> 12: optimization artifacts/backends remain explicit runtime boundaries.
    parity = compare_outputs((0.1, 0.2), (0.1, 0.20001), tolerance=1e-3)
    assert parity.samples == 2

    class TrtRunner:
        def infer(self, inputs):
            return TensorRTExecutionResult("ignored", (sum(inputs),), 1.5)

    class CudaRunner:
        def run(self, inputs):
            return CudaExecutionResult("ignored", (sum(inputs),), 0.5)

    trt = TensorRTExecutionAdapter(TrtRunner(), "engine-test").infer((1.0, 2.0))
    cuda = TimedCudaKernel(CudaRunner(), "kernel-test").run((1.0, 2.0))
    assert trt.engine_id == "engine-test"
    assert cuda.kernel_id == "kernel-test"

    # Phase 13 -> 14: latency/robustness gates are measured, not asserted as hardware evidence.
    latency = EndToEndLatencyHarness(target_ms=50.0).measure(lambda: rollout.frames, iterations=3)
    assert latency.passed
    robustness = SimToRealRobustnessHarness().evaluate(
        "rgb",
        (1.0, 2.0),
        (1.01, 1.99),
        ((0.0, 0.1), (0.1, 0.2)),
        ((0.01, 0.1), (0.1, 0.19)),
        0.95,
    )
    assert robustness.passed

    # Phase 15: physical actuation requires an explicit admission adapter.
    class PhysicalAdmission:
        def admit(self, request: ActuationRequest) -> bool:
            return True

    class Actuator:
        def apply(self, request: ActuationRequest) -> HardwareExecutionEvidence:
            return HardwareExecutionEvidence(
                attempt_id=request.attempt_id,
                device_id=request.device_id,
                sequence=1,
                result_digest="result-digest-1",
                verified=True,
            )

    hil = HardwareInLoopBoundary(PhysicalAdmission(), Actuator())
    hardware_request = ActuationRequest(
        TENANT,
        PROJECT,
        "device-1",
        str(command.attempt_id),
        GovernedHoareClient.digest_request(command, ARTIFACT_HASH),
        {"x": float(command.parameters["x"])},
    )
    hardware_evidence = hil.execute(hardware_request)
    assert hardware_evidence.attempt_id == str(command.attempt_id)

    # Phase 16 -> 17: authority comes from the governance transport, then becomes signed identity.
    admission = GovernedAdmission(True, command.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")

    class GovernanceTransport:
        def admit(self, request):
            assert request.command.command_id == command.command_id
            assert request.artifact_hash == ARTIFACT_HASH
            return admission

    signer = HMACSHA256Signer("test-key", b"test-secret")
    store = InMemoryEvidenceStore()
    verifier = EvidenceVerifier(store)
    boundary = Phase16To17Boundary(GovernedHoareClient(GovernanceTransport()), signer, verifier)
    envelope, signed_admission = boundary.admit_and_sign(
        command,
        ARTIFACT_HASH,
        {"tenant_id": TENANT, "project_id": PROJECT},
        POLICY_DIGEST,
    )
    assert signed_admission.identity.capability_id == admission.capability_id
    assert signed_admission.identity.lease_id == admission.lease_id
    assert signed_admission.identity.fence_id == admission.fence_id
    assert signed_admission.identity.attempt_id == command.attempt_id

    # Phase 17: only verified evidence is committed to a durable receipt.
    evidence = ExecutionEvidence(
        identity_digest=signed_admission.identity_digest,
        attempt_id=command.attempt_id,
        device_id="device-1",
        sequence=1,
        timestamp_ns=1_000,
        result_digest="result-digest-1",
        admission_signature=signed_admission.signature,
    )
    receipt = boundary.commit_evidence(
        envelope,
        signed_admission,
        evidence,
        expected_device_id="device-1",
    )
    assert receipt.identity_digest == signed_admission.identity_digest

    # Phase 18: the durable receipt becomes a tamper-evident chain entry.
    chain_store = InMemoryReceiptChainStore()
    chain = ReceiptChain(chain_store)
    entry = chain.append(
        identity_digest=receipt.identity_digest,
        attempt_id=receipt.attempt_id,
        sequence=receipt.sequence,
        result_digest=receipt.result_digest,
    )
    verification = ReceiptChainVerifier().verify(chain_store.entries())
    assert verification.valid
    assert verification.terminal_digest == entry.chain_digest


def test_phase_16_to_18_rejects_rebound_identity() -> None:
    # Regression guard: a valid signed admission cannot be rebound to a different command attempt.
    command = ControlCommand(
        tenant_id=TENANT,
        project_id=PROJECT,
        command_id=uuid4(),
        attempt_id=uuid4(),
        sequence=1,
        proposed_at=datetime.now(timezone.utc),
        target_id="arm-1",
        command_type="position",
        parameters={"x": 0.1},
        confidence=0.95,
        safety_precondition_ids=("safe",),
        scene_id=uuid4(),
        source_observation_ids=(uuid4(),),
        provenance_uri="urn:test",
    )
    admission = GovernedAdmission(True, command.attempt_id, "cap", "lease", "fence", "admitted")

    class Transport:
        def admit(self, request):
            return admission

    signer = HMACSHA256Signer("key", b"secret")
    verifier = EvidenceVerifier(InMemoryEvidenceStore())
    boundary = Phase16To17Boundary(GovernedHoareClient(Transport()), signer, verifier)
    envelope, artifact = boundary.admit_and_sign(
        command,
        ARTIFACT_HASH,
        {"tenant_id": TENANT, "project_id": PROJECT},
        POLICY_DIGEST,
    )

    rebound = ControlCommand(
        tenant_id=TENANT,
        project_id=PROJECT,
        command_id=uuid4(),
        attempt_id=uuid4(),
        sequence=2,
        proposed_at=datetime.now(timezone.utc),
        target_id="arm-1",
        command_type="position",
        parameters={"x": 0.2},
        confidence=0.95,
        safety_precondition_ids=("safe",),
        scene_id=command.scene_id,
        source_observation_ids=command.source_observation_ids,
        provenance_uri="urn:test",
    )
    with pytest.raises(ValueError, match="attempt"):
        Phase16To17Boundary(
            GovernedHoareClient(Transport()), signer, verifier
        ).admit_and_sign(
            rebound,
            ARTIFACT_HASH,
            {"tenant_id": TENANT, "project_id": PROJECT},
            POLICY_DIGEST,
        )
    assert artifact.identity.attempt_id == envelope.command.attempt_id
