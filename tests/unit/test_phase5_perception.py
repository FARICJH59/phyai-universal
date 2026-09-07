from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.phase1_contracts.contracts import ContractIdentity, SensorObservation
from src.phase5_perception.cuda_kernels.interface import IdentitySpatialAcceleration
from src.phase5_perception.pipeline import PerceptionPipeline


def observation(tenant="t1", project="p1", sequence=1, payload=b"frame"):
    return SensorObservation(
        identity=ContractIdentity(tenant, project, "camera-1", sequence, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        observation_id=uuid4(), sensor_type="camera", frame_id="cam-frame",
        payload=payload, payload_encoding="raw", confidence=0.92,
        calibration_version="cal-v1", provenance_uri="urn:source:camera-1",
    )


def test_perception_builds_spatial_scene_and_preserves_lineage():
    obs = observation(sequence=4)
    scene = PerceptionPipeline().process([obs]).scene
    assert scene.tenant_id == "t1"
    assert scene.project_id == "p1"
    assert scene.sequence == 4
    assert scene.source_observation_ids == (obs.observation_id,)
    assert scene.confidence == 0.92
    assert scene.provenance_uri.startswith("urn:phyai:perception:")


def test_perception_is_deterministic_for_same_observation_ids():
    first = observation(sequence=2)
    second = SensorObservation(
        identity=ContractIdentity("t1", "p1", "depth-1", 3, datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)),
        observation_id=uuid4(), sensor_type="depth", frame_id="depth-frame",
        payload=b"depth", payload_encoding="raw", confidence=0.88,
        calibration_version="cal-v2", provenance_uri="urn:source:depth-1",
    )
    a = PerceptionPipeline().process([second, first]).scene
    b = PerceptionPipeline().process([first, second]).scene
    assert a.scene_id == b.scene_id
    assert a.representation == b.representation
    assert a.source_observation_ids == b.source_observation_ids


def test_cross_tenant_perception_fails_closed():
    with pytest.raises(ValueError, match="cross-tenant"):
        PerceptionPipeline().process([observation("t1"), observation("t2")])


def test_cross_project_perception_fails_closed():
    with pytest.raises(ValueError, match="cross-project"):
        PerceptionPipeline().process([observation("t1", "p1"), observation("t1", "p2")])


def test_identity_acceleration_preserves_representation():
    payload = b"spatial"
    assert IdentitySpatialAcceleration().accelerate(payload) == payload


def test_perception_has_no_execution_authority():
    scene = PerceptionPipeline().process([observation()]).scene
    assert not hasattr(scene, "lease")
    assert not hasattr(scene, "capability")
    assert not hasattr(scene, "authorization")
