from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.phase1_contracts.contracts import SensorObservation, SpatialScene
from src.phase2_sensors.fusion.observation_fusion import ObservationFusion
from src.phase5_perception.cuda_kernels.interface import IdentitySpatialAcceleration, SpatialAcceleration
from src.phase5_perception.vggt.adapter import ReferenceVGGTPredictor, SpatialPrediction, VGGTPredictor


@dataclass(frozen=True, slots=True)
class PerceptionPrediction:
    scene: SpatialScene


class PerceptionPipeline:
    """Converts canonical observations into spatial scenes, without authority."""

    def __init__(self, predictor: VGGTPredictor | None = None, accelerator: SpatialAcceleration | None = None):
        self._predictor = predictor or ReferenceVGGTPredictor()
        self._accelerator = accelerator or IdentitySpatialAcceleration()
        self._fusion = ObservationFusion()

    def process(self, observations: Sequence[SensorObservation]) -> PerceptionPrediction:
        ordered = self._fusion.fuse(observations)
        prediction: SpatialPrediction = self._predictor.predict(ordered)
        representation = self._accelerator.accelerate(prediction.representation)
        first = ordered[0]
        scene = SpatialScene(
            tenant_id=first.identity.tenant_id,
            project_id=first.identity.project_id,
            scene_id=prediction.scene_id,
            sequence=prediction.sequence,
            observed_at=prediction.observed_at,
            reference_frame=prediction.reference_frame,
            representation=representation,
            representation_encoding="json",
            confidence=prediction.confidence,
            source_observation_ids=prediction.source_observation_ids,
            provenance_uri=f"urn:phyai:perception:{prediction.scene_id}",
        )
        return PerceptionPrediction(scene=scene)
