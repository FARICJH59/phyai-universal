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
from src.production_hardening.phase16_hoare_integration import GovernedAdmission, GovernedExecutionRequest, GovernedHoareClient
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


def test_runtime_spine_preserves_identity_and_authority_order() -> None:
    """Verify the runtime dependency graph without treating phase numbers as runtime order."""
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

    # Phase 5: canonical observations become a spatial scene.
    scene = PerceptionPipeline().process((observation,)).scene
    assert scene.tenant_id == TENANT
    assert scene.project_id == PROJECT
    assert observation.observation_id in scene.source_observation_ids

    # Phase 7 is reasoning-before-control at runtime: it produces a plan, not authority.
    reasoning = ReasoningPipeline().reason(
        scene,
        objective="track target",
        target_id="arm-1",
        command_type="position",
        safety_precondition_ids=("precondition-safe",),
        constraints={"target_position": 0.8, "max_acceleration": 1.0},
    )
    assert reasoning.scene_id == scene.scene_id
    assert reasoning.authorization_required is True

    # Phase 3/4 provide deterministic simulation and surrogate support for the plan.
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

    # Phase 9: action-conditioned learned-world-model boundary remains identity-bound.
    action = ActionCondition(reasoning.plan.command_type, {"acceleration": float(solution.values["acceleration"])})
    world_request = LearnedWorldModelRequest(
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
        model_id = "test-learned-model"

        def predict(self, model_input: TensorWorldModelInput):
            assert len(model_input.action_features) == model_input.horizon
            return ((0.1,), (0.2,))

    rollout = EncodedLearnedWorldModelAdapter(LearnedModel(), Encoder()).predict(world_request)
    assert rollout.tenant_id == TENANT
    assert rollout.project_id == PROJECT
    assert rollout.scene_id == scene.scene_id
    assert len(rollout.frames) == 2

    # Phase 10: multimodal learned representation preserves temporal modality order.
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

    # Phase 6: the reasoning plan becomes an authorization-free control proposal.
    command = ControlPipeline().propose(
        scene,
        target_id=reasoning.plan.target_id,
        command_type=reasoning.plan.command_type,
        parameters=reasoning.plan.parameters,
        safety_precondition_ids=tuple(reasoning.plan.safety_precondition_ids),
    )
    assert command.is_authorization_free_proposal
    assert command.tenant_id == TENANT
    assert command.project_id == PROJECT
    assert command.scene_id == scene.scene_id
    assert command.source_observation_ids == tuple(scene.source_observation_ids)

    # Phase 8: evaluation consumes the proposal but does not authorize it.
    evaluation = DeterministicEvaluator().evaluate(scene, command, {"x": command.parameters.get("x", 0.0)})
    assert evaluation.passed

    # Phases 11/12: backend/parity boundaries remain explicit; injected runners stand in for real runtimes.
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

    # Phases 13/14: latency and robustness are gates, not claims of hardware evidence.
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

    # Phase 15: define the physical boundary, but do not execute before governed admission.
    class PhysicalAdmission:
        def admit(self, request: ActuationRequest) -> bool:
            return request.command_digest == GovernedHoareClient.digest_request(command, ARTIFACT_HASH)

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

    # Phase 16: authority is minted by the governance transport.
    admission = GovernedAdmission(True, command.attempt_id, "cap-1", "lease-1", "fence-1", "admitted")

    class GovernanceTransport:
        def admit(self, request: GovernedExecutionRequest):
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

    # Only after Phase 16 admission does the Phase 15 boundary execute physical I/O.
    hardware_request = ActuationRequest(
        TENANT,
        PROJECT,
        "device-1",
        str(command.attempt_id),
        GovernedHoareClient.digest_request(command, ARTIFACT_HASH),
        {"x": float(command.parameters.get("x", 0.0))},
    )
    hardware_evidence = hil.execute(hardware_request)
    assert hardware_evidence.attempt_id == str(command.attempt_id)

    # Phase 17: execution evidence must bind the signed Phase 16 identity before receipt creation.
    evidence = ExecutionEvidence(
        identity_digest=signed_admission.identity_digest,
        attempt_id=command.attempt_id,
        device_id="device-1",
        sequence=1,
        timestamp_ns=1_000,
        result_digest=hardware_evidence.result_digest,
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


def test_denied_governance_stops_before_phase17_and_physical_execution():
    command_id = uuid4()
    attempt_id = uuid4()
    from src.phase1_contracts.contracts import ControlCommand

    command = ControlCommand(
        tenant_id=TENANT,
        project_id=PROJECT,
        command_id=command_id,
        attempt_id=attempt_id,
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

    class DenyingTransport:
        def admit(self, request):
            return GovernedAdmission(False, request.command.attempt_id, None, None, None, "denied")

    boundary = Phase16To17Boundary(
        GovernedHoareClient(DenyingTransport()),
        HMACSHA256Signer("key", b"secret"),
        EvidenceVerifier(InMemoryEvidenceStore()),
    )
    with pytest.raises(PermissionError):
        boundary.admit_and_sign(
            command,
            ARTIFACT_HASH,
            {"tenant_id": TENANT, "project_id": PROJECT},
            POLICY_DIGEST,
        )


def test_cross_tenant_data_cannot_enter_perception_spine():
    adapter = SensorAdapter()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observations = (
        adapter.ingest(
            RawSensorSample(
                TENANT,
                PROJECT,
                "camera-1",
                1,
                "rgb",
                "frame-1",
                b"one",
                "raw",
                "cal-v1",
                "urn:test:one",
                0.98,
                now,
            )
        ),
        adapter.ingest(
            RawSensorSample(
                "tenant-b",
                PROJECT,
                "camera-2",
                2,
                "rgb",
                "frame-2",
                b"two",
                "raw",
                "cal-v1",
                "urn:test:two",
                0.98,
                now,
            )
        ),
    )
    with pytest.raises(ValueError):
        PerceptionPipeline().process(observations)
