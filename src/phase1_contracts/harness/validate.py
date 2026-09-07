from datetime import datetime, timezone
from uuid import uuid4

from src.phase1_contracts.contracts import ContractIdentity, ControlCommand, SensorObservation, SpatialScene


def smoke_validate() -> None:
    now = datetime.now(timezone.utc)
    identity = ContractIdentity("tenant", "project", "sensor", 0, now)
    observation = SensorObservation(identity, uuid4(), "camera", "base", b"sample", "raw", 1.0, "cal-1", "evidence://sample")
    scene = SpatialScene("tenant", "project", uuid4(), 0, now, "map", b"scene", "opaque", 0.9, [observation.observation_id], "evidence://scene")
    command = ControlCommand("tenant", "project", uuid4(), uuid4(), 0, now, "target", "noop", {"value": 0}, 0.9, ["safe"], scene.scene_id, [observation.observation_id], "evidence://command")
    assert command.is_authorization_free_proposal


if __name__ == "__main__":
    smoke_validate()
    print("PHyAI Phase 1 contract smoke validation: PASS")
