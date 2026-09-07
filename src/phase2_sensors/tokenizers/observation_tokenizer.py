from src.phase1_contracts.contracts import SensorObservation


class ObservationTokenizer:
    """Deterministic metadata tokenizer; raw sensor bytes remain opaque."""

    def tokenize(self, observation: SensorObservation) -> list[str]:
        identity = observation.identity
        return [
            f"tenant:{identity.tenant_id}",
            f"project:{identity.project_id}",
            f"source:{identity.source_id}",
            f"sensor:{observation.sensor_type}",
            f"frame:{observation.frame_id}",
            f"encoding:{observation.payload_encoding}",
            f"calibration:{observation.calibration_version}",
            f"sequence:{identity.sequence}",
            f"confidence:{observation.confidence:.6f}",
        ]
