from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence
from uuid import UUID, uuid5

from src.phase1_contracts.contracts import SensorObservation


@dataclass(frozen=True, slots=True)
class SpatialPrediction:
    scene_id: UUID
    reference_frame: str
    representation: bytes
    confidence: float
    observed_at: datetime
    sequence: int
    source_observation_ids: tuple[UUID, ...]


class VGGTPredictor(Protocol):
    """Model boundary for VGGT-compatible spatial reconstruction."""

    def predict(self, observations: Sequence[SensorObservation]) -> SpatialPrediction: ...


class ReferenceVGGTPredictor:
    """Deterministic contract-test backend; it is not trained VGGT inference."""

    NAMESPACE = UUID("4b5c1d73-1e48-4f9c-9c38-1c3c6e5e7f01")

    def predict(self, observations: Sequence[SensorObservation]) -> SpatialPrediction:
        if not observations:
            raise ValueError("observations must not be empty")
        tenant = observations[0].identity.tenant_id
        project = observations[0].identity.project_id
        if any(o.identity.tenant_id != tenant or o.identity.project_id != project for o in observations):
            raise ValueError("cross-tenant or cross-project perception is forbidden")

        ordered = tuple(sorted(observations, key=lambda o: (o.identity.sequence, str(o.observation_id))))
        source_ids = tuple(o.observation_id for o in ordered)
        sequence = max(o.identity.sequence for o in ordered)
        observed_at = max(o.identity.observed_at for o in ordered).astimezone(timezone.utc)
        confidence = min(o.confidence for o in ordered)
        scene_key = f"{tenant}|{project}|{sequence}|" + "|".join(map(str, source_ids))
        scene_id = uuid5(self.NAMESPACE, scene_key)

        records = []
        for o in ordered:
            records.append({
                "observation_id": str(o.observation_id),
                "sensor_type": o.sensor_type,
                "frame_id": o.frame_id,
                "sequence": o.identity.sequence,
                "observed_at": o.identity.observed_at.isoformat(),
                "payload_sha256": hashlib.sha256(o.payload).hexdigest(),
                "payload_encoding": o.payload_encoding,
                "calibration_version": o.calibration_version,
                "confidence": o.confidence,
            })
        representation = json.dumps({"schema": "phase5-reference-spatial-v1", "observations": records}, sort_keys=True, separators=(",", ":")).encode()
        return SpatialPrediction(scene_id, "world", representation, confidence, observed_at, sequence, source_ids)
