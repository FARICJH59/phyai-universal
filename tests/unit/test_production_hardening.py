from datetime import datetime, timezone
from math import sqrt
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import (
    ControlCommand,
    ContractIdentity,
    SensorObservation,
)
from src.production_hardening.hoare_boundary import (
    AdmissionDecision,
    ExecutionProposal,
    HoareExecutionBoundary,
)
from src.production_hardening.multimodal import ModalityInput, MultimodalFusion
from src.production_hardening.robustness import MultimodalPerturbation, SensorNoiseHarness
from src.production_hardening.trajectory import AutoregressiveTrajectoryGenerator
from src.production_hardening.world_model import ActionCondition, ActionConditionedReferenceWorldModel, WorldModelRequest


def observation(tenant: str = "t1", project: str = "p1", seq: int = 1) -> SensorObservation:
    return SensorObservation(
        identity=ContractIdentity(tenant, project, "camera", seq, datetime.now(timezone.utc)),
        observation_id=uuid4(), sensor_type="rgbd", frame_id="base",
        payload=b"frame", payload_encoding="raw", confidence=0.99,
        calibration_version="cal-1", provenance_uri="urn:test:frame",
    )


def command() -> ControlCommand:
    obs = observation()
    return ControlCommand(
        tenant_id="t1", project_id="p1", command_id=uuid4(), attempt_id=uuid4(),
        sequence=1, proposed_at=datetime.now(timezone.utc), target_id="arm",
        command_type="joint_velocity", parameters={"joint_1": 0.1}, confidence=0.95,
        safety_precondition_ids=("workspace-safe",), scene_id=uuid4(),
        source_observation_ids=(obs.observation_id,), provenance_uri="urn:test:command",
    )


def test_action_conditioned_rollout_is_deterministic_and_autoregressive():
    request = WorldModelRequest("t1", "p1", uuid4(), {"position": 0.0, "velocity": 0.0}, ActionCondition("move", {"acceleration": 1.0}), 3)
    model = ActionConditionedReferenceWorldModel()
    first = model.rollout(request)
    second = model.rollout(request)
    assert first == second
    trajectory = AutoregressiveTrajectoryGenerator(model).generate(request)
    assert [s["position"] for s in trajectory.states] == [1.0, 3.0, 6.0]


def test_multimodal_fusion_preserves_all_modalities_and_is_deterministic():
    inputs = [
        ModalityInput("rgb", b"rgb", "jpeg", 10, 0.98),
        ModalityInput("depth", b"depth", "float32", 11, 0.96),
        ModalityInput("proprioception", b"joints", "float32", 12, 0.99),
        ModalityInput("tactile", b"touch", "float32", 13, 0.93),
        ModalityInput("language", b"pick", "utf8", 14, 0.90),
    ]
    fusion = MultimodalFusion()
    first = fusion.fuse("t1", "p1", inputs)
    second = fusion.fuse("t1", "p1", inputs)
    assert first == second
    assert first.modality_order == ("rgb", "depth", "proprioception", "tactile", "language")
    assert first.confidence == 0.90


def test_multimodal_fusion_rejects_empty_inputs():
    with pytest.raises(ValueError):
        MultimodalFusion().fuse("t1", "p1", [])


def test_noise_harness_detects_perturbation():
    case = SensorNoiseHarness.bit_flip()
    result = SensorNoiseHarness.evaluate(b"sensor-frame", case)
    assert result.changed is True


def test_output_sensitivity_measures_delta_and_confidence_degradation():
    result = SensorNoiseHarness.evaluate_output([1.0, 2.0], [1.0, 2.5], 0.95, 0.80)
    assert result.l2_delta == pytest.approx(0.5)
    assert result.relative_delta == pytest.approx(0.5 / sqrt(5.0))
    assert result.confidence_degradation == pytest.approx(0.15)


def test_trajectory_deviation_measures_mean_and_max_error():
    result = SensorNoiseHarness.evaluate_trajectory(
        [{"position": 1.0}, {"position": 3.0}],
        [{"position": 1.2}, {"position": 2.5}],
        0.90,
        0.70,
    )
    assert result.samples == 2
    assert result.mean_l2_error == pytest.approx(0.35)
    assert result.maximum_l2_error == pytest.approx(0.5)
    assert result.confidence_degradation == pytest.approx(0.20)


def test_multimodal_perturbation_changes_only_selected_modality():
    modalities = {"rgb": b"rgb", "depth": b"depth"}
    result = SensorNoiseHarness.perturb_modalities(
        modalities, [MultimodalPerturbation("depth", SensorNoiseHarness.bit_flip())]
    )
    assert result["rgb"] == b"rgb"
    assert result["depth"] != b"depth"


def test_robustness_rejects_mismatched_output_lengths():
    with pytest.raises(ValueError):
        SensorNoiseHarness.evaluate_output([1.0], [1.0, 2.0], 0.9, 0.9)


def test_robustness_rejects_mismatched_trajectory_shapes():
    with pytest.raises(ValueError):
        SensorNoiseHarness.evaluate_trajectory([{"x": 1.0}], [{"y": 1.0}], 0.9, 0.9)


def test_hoare_boundary_enforces_tenant_and_project_context_before_submission():
    class Client:
        def submit_proposal(self, proposal):
            return AdmissionDecision(True, proposal.command.attempt_id, "admitted")

    boundary = HoareExecutionBoundary(Client())
    proposal = ExecutionProposal(command(), "artifact-sha", {"tenant_id": "t1", "project_id": "p1"})
    assert boundary.submit(proposal).accepted is True
    bad = ExecutionProposal(command(), "artifact-sha", {"tenant_id": "other", "project_id": "p1"})
    with pytest.raises(PermissionError):
        boundary.submit(bad)


def test_control_command_remains_authorization_free():
    assert command().is_authorization_free_proposal is True
