from datetime import datetime, timezone

import pytest

from src.phase2_sensors.sensor_adapter import RawSensorSample, SensorAdapter
from src.phase2_sensors.normalizer import SensorNormalizer
from src.phase2_sensors.tokenizers.observation_tokenizer import ObservationTokenizer
from src.phase2_sensors.fusion.observation_fusion import ObservationFusion

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def sample(source="camera-1", sequence=1, tenant="tenant-a", project="project-a"):
    return RawSensorSample(tenant, project, source, sequence, "camera", "base", b"frame", "raw", "cal-1", "evidence://1", 0.95, NOW)


def test_adapter_normalizes_to_phase1_contract():
    observation = SensorAdapter().ingest(sample())
    assert observation.identity.tenant_id == "tenant-a"
    assert observation.identity.sequence == 1


def test_tokenizer_is_deterministic_for_same_observation():
    observation = SensorAdapter().ingest(sample())
    tokenizer = ObservationTokenizer()
    assert tokenizer.tokenize(observation) == tokenizer.tokenize(observation)


def test_fusion_rejects_cross_tenant_samples():
    adapter = SensorAdapter()
    a = adapter.ingest(sample(tenant="tenant-a"))
    b = adapter.ingest(sample(source="camera-2", tenant="tenant-b"))
    with pytest.raises(ValueError, match="cross-tenant"):
        ObservationFusion().fuse([a, b])


def test_fusion_orders_by_sequence():
    adapter = SensorAdapter()
    a = adapter.ingest(sample(sequence=2))
    b = adapter.ingest(sample(source="camera-2", sequence=1))
    result = ObservationFusion().fuse([a, b])
    assert [item.identity.sequence for item in result] == [1, 2]
