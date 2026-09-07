from dataclasses import dataclass
from uuid import UUID, uuid5

from ..contracts import SimulationState


_NAMESPACE = UUID("5a7e2b7f-31b8-4f12-8c6f-8c0f5bbd0a21")


@dataclass(frozen=True, slots=True)
class ScenarioGenerator:
    """Generate reproducible initial states without external randomness."""

    environment_id: str = "reference"

    def generate(self, tenant_id: str, project_id: str, seed: int) -> SimulationState:
        if seed < 0:
            raise ValueError("seed must be non-negative")
        scenario_id = uuid5(_NAMESPACE, f"{tenant_id}:{project_id}:{self.environment_id}:{seed}")
        # Deterministic, bounded reference state. Real simulators can replace this generator.
        position = ((seed * 1103515245 + 12345) % 10000) / 10000.0
        velocity = (((seed + 17) * 214013 + 2531011) % 10000) / 10000.0
        return SimulationState(
            tenant_id=tenant_id,
            project_id=project_id,
            scenario_id=scenario_id,
            environment_id=self.environment_id,
            step=0,
            state={"position": position, "velocity": velocity},
            seed=seed,
        )
