from datetime import datetime, timezone

import pytest

from src.adapters.mqtt.contracts import (
    AuthenticatedMqttPrincipal,
    IngressOutcome,
    IngressStatus,
    MqttContractError,
    MqttObservationEnvelope,
    MqttTransportMetadata,
    RegisteredDeviceIdentity,
)

NOW = datetime(2026, 10, 31, 6, 34, tzinfo=timezone.utc)


def envelope(**overrides):
    values = {
        "event_id": "evt-001",
        "schema_version": "v1",
        "source_sequence": 7,
        "sensor_type": "temperature",
        "frame_id": "sensor-frame",
        "observed_at": NOW,
        "payload": b"21.5",
        "payload_encoding": "text/plain",
        "calibration_version": "cal-3",
        "provenance_uri": "evidence://device-1/evt-001",
        "confidence": 0.98,
    }
    values.update(overrides)
    return MqttObservationEnvelope(**values)


def test_envelope_is_transport_neutral_and_has_no_tenant_authority():
    item = envelope()
    assert item.event_id == "evt-001"
    assert not hasattr(item, "tenant_id")
    assert not hasattr(item, "project_id")
    assert not hasattr(item, "source_id")


@pytest.mark.parametrize("sequence", [-1, True, 1.5])
def test_envelope_rejects_invalid_sequence(sequence):
    with pytest.raises(MqttContractError, match="source_sequence"):
        envelope(source_sequence=sequence)


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -0.01, 1.01, True])
def test_envelope_rejects_invalid_confidence(confidence):
    with pytest.raises(MqttContractError, match="confidence"):
        envelope(confidence=confidence)


def test_envelope_rejects_naive_timestamp_and_empty_payload():
    with pytest.raises(MqttContractError, match="timezone-aware"):
        envelope(observed_at=datetime(2026, 10, 31))
    with pytest.raises(MqttContractError, match="non-empty bytes"):
        envelope(payload=b"")


def test_authenticated_principal_and_transport_metadata_are_distinct():
    principal = AuthenticatedMqttPrincipal("cert:device-1", "device-client-1")
    transport = MqttTransportMetadata(
        topic="phyai/v1/tenants/t1/projects/p1/devices/d1/sensors/s1/observations",
        qos=1,
        retain=False,
        received_at=NOW,
    )
    assert principal.principal_id == "cert:device-1"
    assert transport.qos == 1
    assert transport.retain is False


def test_transport_rejects_invalid_qos_and_naive_receive_time():
    with pytest.raises(MqttContractError, match="qos"):
        MqttTransportMetadata("topic", 3, False, NOW)
    with pytest.raises(MqttContractError, match="timezone-aware"):
        MqttTransportMetadata("topic", 1, False, datetime(2026, 10, 31))


def test_registered_identity_is_a_trusted_registry_scope():
    identity = RegisteredDeviceIdentity(
        principal_id="cert:device-1",
        client_id="device-client-1",
        tenant_id="tenant-a",
        project_id="project-a",
        source_id="edge-node-1",
        device_id="device-1",
        allowed_sensor_ids=frozenset({"sensor-1"}),
        allowed_topic_prefix="phyai/v1/tenants/tenant-a/projects/project-a/",
    )
    assert identity.tenant_id == "tenant-a"
    assert identity.allowed_sensor_ids == frozenset({"sensor-1"})


def test_ingress_outcome_requires_rejection_reason():
    assert IngressOutcome(IngressStatus.ACCEPTED, event_id="evt-001").status is IngressStatus.ACCEPTED
    with pytest.raises(MqttContractError, match="reason_code"):
        IngressOutcome(IngressStatus.REJECTED_AUTH, event_id="evt-001")
    with pytest.raises(MqttContractError, match="rejection reason"):
        IngressOutcome(IngressStatus.DUPLICATE, event_id="evt-001", reason_code="already_seen")
