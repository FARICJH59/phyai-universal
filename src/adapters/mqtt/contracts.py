"""Broker-neutral contracts for authenticated MQTT telemetry ingress.

Created: 2026-10-31T06:34:00-04:00
EMQX-2: contracts only; no broker client or network behavior.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol


class MqttContractError(ValueError):
    """Raised when an MQTT ingress contract is structurally invalid."""


def _required(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise MqttContractError(f"{field_name} is required")


def _aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MqttContractError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AuthenticatedMqttPrincipal:
    """Identity asserted by the authenticated broker session, not message data."""

    principal_id: str
    client_id: str

    def __post_init__(self) -> None:
        _required(self.principal_id, "principal_id")
        _required(self.client_id, "client_id")


@dataclass(frozen=True, slots=True)
class MqttTransportMetadata:
    """Transport facts supplied by the broker integration boundary."""

    topic: str
    qos: int
    retain: bool
    received_at: datetime
    broker_message_id: str | None = None

    def __post_init__(self) -> None:
        _required(self.topic, "topic")
        if self.qos not in (0, 1, 2):
            raise MqttContractError("qos must be 0, 1 or 2")
        if not isinstance(self.retain, bool):
            raise MqttContractError("retain must be boolean")
        _aware(self.received_at, "received_at")
        if self.broker_message_id is not None:
            _required(self.broker_message_id, "broker_message_id")


@dataclass(frozen=True, slots=True)
class MqttObservationEnvelope:
    """Transport-neutral observation envelope; contains no trusted tenant identity."""

    event_id: str
    schema_version: str
    source_sequence: int
    sensor_type: str
    frame_id: str
    observed_at: datetime
    payload: bytes
    payload_encoding: str
    calibration_version: str
    provenance_uri: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        for name in (
            "event_id", "schema_version", "sensor_type", "frame_id",
            "payload_encoding", "calibration_version", "provenance_uri",
        ):
            _required(getattr(self, name), name)
        if isinstance(self.source_sequence, bool) or not isinstance(self.source_sequence, int) or self.source_sequence < 0:
            raise MqttContractError("source_sequence must be a non-negative integer")
        _aware(self.observed_at, "observed_at")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise MqttContractError("payload must be non-empty bytes")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise MqttContractError("confidence must be numeric")
        # Range comparison rejects NaN; explicit bounds reject infinities.
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise MqttContractError("confidence must be finite and between 0 and 1")


@dataclass(frozen=True, slots=True)
class RegisteredDeviceIdentity:
    """Trusted registry result scoped to one device and its permitted sensors."""

    principal_id: str
    client_id: str
    tenant_id: str
    project_id: str
    source_id: str
    device_id: str
    allowed_sensor_ids: frozenset[str]
    allowed_topic_prefix: str

    def __post_init__(self) -> None:
        for name in (
            "principal_id", "client_id", "tenant_id", "project_id",
            "source_id", "device_id", "allowed_topic_prefix",
        ):
            _required(getattr(self, name), name)
        if not self.allowed_sensor_ids:
            raise MqttContractError("allowed_sensor_ids must not be empty")
        for sensor_id in self.allowed_sensor_ids:
            _required(sensor_id, "allowed_sensor_id")


class DeviceIdentityResolver(Protocol):
    """Resolves broker-authenticated identity using a trusted device registry."""

    def resolve(
        self, principal: AuthenticatedMqttPrincipal
    ) -> RegisteredDeviceIdentity | None:
        """Return the registered identity or None when the principal is unknown."""


class IngressStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED_AUTH = "REJECTED_AUTH"
    REJECTED_SCHEMA = "REJECTED_SCHEMA"
    REJECTED_METADATA = "REJECTED_METADATA"
    REJECTED_LIMIT = "REJECTED_LIMIT"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True, slots=True)
class IngressOutcome:
    """Typed adapter outcome; deliberately carries no actuator/execution capability."""

    status: IngressStatus
    event_id: str | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.event_id is not None:
            _required(self.event_id, "event_id")
        if self.reason_code is not None:
            _required(self.reason_code, "reason_code")
        if self.status in (IngressStatus.REJECTED_AUTH, IngressStatus.REJECTED_SCHEMA,
                           IngressStatus.REJECTED_METADATA, IngressStatus.REJECTED_LIMIT,
                           IngressStatus.QUARANTINED) and self.reason_code is None:
            raise MqttContractError("non-accepted outcomes require a reason_code")
        if self.status in (IngressStatus.ACCEPTED, IngressStatus.DUPLICATE) and self.reason_code is not None:
            raise MqttContractError("accepted/duplicate outcomes must not carry a rejection reason")
