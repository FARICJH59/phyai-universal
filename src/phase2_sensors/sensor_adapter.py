from dataclasses import dataclass
from datetime import datetime

from .normalizer import SensorNormalizer
from src.phase1_contracts.contracts import SensorObservation


@dataclass(frozen=True, slots=True)
class RawSensorSample:
    tenant_id: str
    project_id: str
    source_id: str
    sequence: int
    sensor_type: str
    frame_id: str
    payload: bytes
    payload_encoding: str
    calibration_version: str
    provenance_uri: str
    confidence: float = 1.0
    observed_at: datetime | None = None


class SensorAdapter:
    """Stable adapter boundary between physical drivers and PHyAI contracts."""

    def __init__(self, normalizer: SensorNormalizer | None = None):
        self._normalizer = normalizer or SensorNormalizer()

    def ingest(self, sample: RawSensorSample) -> SensorObservation:
        return self._normalizer.normalize(
            tenant_id=sample.tenant_id,
            project_id=sample.project_id,
            source_id=sample.source_id,
            sequence=sample.sequence,
            sensor_type=sample.sensor_type,
            frame_id=sample.frame_id,
            payload=sample.payload,
            payload_encoding=sample.payload_encoding,
            calibration_version=sample.calibration_version,
            provenance_uri=sample.provenance_uri,
            confidence=sample.confidence,
            observed_at=sample.observed_at,
        )
