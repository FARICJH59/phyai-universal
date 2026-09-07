from collections.abc import Sequence

from src.phase1_contracts.contracts import SensorObservation


class ObservationFusion:
    """Groups observations without inventing a second identity model."""

    def validate_batch(self, observations: Sequence[SensorObservation]) -> None:
        if not observations:
            raise ValueError("observation batch must not be empty")
        first = observations[0].identity
        for item in observations:
            if item.identity.tenant_id != first.tenant_id:
                raise ValueError("cross-tenant observation fusion is forbidden")
            if item.identity.project_id != first.project_id:
                raise ValueError("cross-project observation fusion is forbidden")

    def fuse(self, observations: Sequence[SensorObservation]) -> tuple[SensorObservation, ...]:
        self.validate_batch(observations)
        return tuple(sorted(observations, key=lambda item: (item.identity.sequence, str(item.observation_id))))
