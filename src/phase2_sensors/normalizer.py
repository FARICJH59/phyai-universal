from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.phase1_contracts.contracts import ContractIdentity, SensorObservation


class SensorNormalizationError(ValueError):
    pass


class SensorNormalizer:
    """Converts adapter output into the canonical Phase 1 observation contract."""

    def normalize(
        self,
        *,
        tenant_id: str,
        project_id: str,
        source_id: str,
        sequence: int,
        sensor_type: str,
        frame_id: str,
        payload: bytes,
        payload_encoding: str,
        calibration_version: str,
        provenance_uri: str,
        confidence: float = 1.0,
        observation_id: UUID | None = None,
        observed_at: datetime | None = None,
    ) -> SensorObservation:
        timestamp = observed_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise SensorNormalizationError("observed_at must be timezone-aware")
        return SensorObservation(
            identity=ContractIdentity(
                tenant_id=tenant_id,
                project_id=project_id,
                source_id=source_id,
                sequence=sequence,
                observed_at=timestamp,
            ),
            observation_id=observation_id or uuid4(),
            sensor_type=sensor_type,
            frame_id=frame_id,
            payload=payload,
            payload_encoding=payload_encoding,
            confidence=confidence,
            calibration_version=calibration_version,
            provenance_uri=provenance_uri,
        )
