from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Sequence
from uuid import UUID

class ContractValidationError(ValueError):
    pass

def _required(value: str, name: str) -> str:
    if not value or not value.strip():
        raise ContractValidationError(f"{name} is required")
    return value.strip()

def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractValidationError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)

def _confidence(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ContractValidationError("confidence must be between 0 and 1")
    return value

@dataclass(frozen=True, slots=True)
class ContractIdentity:
    tenant_id: str
    project_id: str
    source_id: str
    sequence: int
    observed_at: datetime
    schema_version: str = "v1"
    def __post_init__(self):
        for name in ("tenant_id", "project_id", "source_id", "schema_version"):
            _required(getattr(self, name), name)
        if self.sequence < 0:
            raise ContractValidationError("sequence must be non-negative")
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))

@dataclass(frozen=True, slots=True)
class SensorObservation:
    identity: ContractIdentity
    observation_id: UUID
    sensor_type: str
    frame_id: str
    payload: bytes
    payload_encoding: str
    confidence: float
    calibration_version: str
    provenance_uri: str
    def __post_init__(self):
        for name in ("sensor_type", "frame_id", "payload_encoding", "calibration_version", "provenance_uri"):
            _required(getattr(self, name), name)
        if not isinstance(self.payload, bytes) or not self.payload:
            raise ContractValidationError("payload must be non-empty bytes")
        _confidence(self.confidence)

@dataclass(frozen=True, slots=True)
class SpatialScene:
    tenant_id: str
    project_id: str
    scene_id: UUID
    sequence: int
    observed_at: datetime
    reference_frame: str
    representation: bytes
    representation_encoding: str
    confidence: float
    source_observation_ids: Sequence[UUID] = field(default_factory=tuple)
    provenance_uri: str = ""
    schema_version: str = "v1"
    def __post_init__(self):
        for name in ("tenant_id", "project_id", "reference_frame", "representation_encoding"):
            _required(getattr(self, name), name)
        if self.sequence < 0 or not self.representation or not self.source_observation_ids:
            raise ContractValidationError("invalid spatial scene")
        _confidence(self.confidence)
        _utc(self.observed_at, "observed_at")

@dataclass(frozen=True, slots=True)
class ControlCommand:
    tenant_id: str
    project_id: str
    command_id: UUID
    attempt_id: UUID
    sequence: int
    proposed_at: datetime
    target_id: str
    command_type: str
    parameters: Mapping[str, object]
    confidence: float
    safety_precondition_ids: Sequence[str]
    scene_id: UUID
    source_observation_ids: Sequence[UUID]
    provenance_uri: str
    schema_version: str = "v1"
    def __post_init__(self):
        for name in ("tenant_id", "project_id", "target_id", "command_type", "provenance_uri"):
            _required(getattr(self, name), name)
        if self.sequence < 0 or not self.parameters or not self.safety_precondition_ids or not self.source_observation_ids:
            raise ContractValidationError("invalid control command")
        _confidence(self.confidence)
        _utc(self.proposed_at, "proposed_at")

    @property
    def is_authorization_free_proposal(self) -> bool:
        return True
