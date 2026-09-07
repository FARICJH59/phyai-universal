from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from src.phase1_contracts.contracts.contracts import ContractValidationError


@dataclass(frozen=True, slots=True)
class SimulationState:
    tenant_id: str
    project_id: str
    scenario_id: UUID
    environment_id: str
    step: int
    state: Mapping[str, float]
    seed: int

    def __post_init__(self):
        if not self.tenant_id.strip() or not self.project_id.strip():
            raise ContractValidationError("tenant_id and project_id are required")
        if not self.environment_id.strip():
            raise ContractValidationError("environment_id is required")
        if self.step < 0:
            raise ContractValidationError("step must be non-negative")
        if self.seed < 0:
            raise ContractValidationError("seed must be non-negative")
        if not self.state:
            raise ContractValidationError("state must be non-empty")


@dataclass(frozen=True, slots=True)
class SimulationAction:
    """A simulator-local action; it carries no execution authority."""

    target_id: str
    command_type: str
    parameters: Mapping[str, float]

    def __post_init__(self):
        if not self.target_id.strip() or not self.command_type.strip():
            raise ContractValidationError("target_id and command_type are required")
        if not self.parameters:
            raise ContractValidationError("parameters must be non-empty")


@dataclass(frozen=True, slots=True)
class SimulationResult:
    previous: SimulationState
    next_state: SimulationState
    reward: float
    terminated: bool
    diagnostics: Mapping[str, float]

    def __post_init__(self):
        if self.previous.tenant_id != self.next_state.tenant_id:
            raise ContractValidationError("simulation result crosses tenants")
        if self.previous.project_id != self.next_state.project_id:
            raise ContractValidationError("simulation result crosses projects")
        if self.next_state.step != self.previous.step + 1:
            raise ContractValidationError("simulation step must advance exactly once")
