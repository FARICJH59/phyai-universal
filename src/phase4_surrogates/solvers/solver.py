from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence
from uuid import UUID

from src.phase1_contracts.contracts.contracts import ContractValidationError
from src.phase3_simulation.contracts import SimulationState


@dataclass(frozen=True, slots=True)
class SolverRequest:
    tenant_id: str
    project_id: str
    scenario_id: UUID
    objective: str
    state: SimulationState
    constraints: Mapping[str, float]

    def __post_init__(self):
        if not self.tenant_id.strip() or not self.project_id.strip():
            raise ContractValidationError("tenant_id and project_id are required")
        if self.state.tenant_id != self.tenant_id or self.state.project_id != self.project_id:
            raise ContractValidationError("solver request crosses tenant or project boundary")
        if self.state.scenario_id != self.scenario_id:
            raise ContractValidationError("solver request scenario mismatch")
        if not self.objective.strip():
            raise ContractValidationError("objective is required")


@dataclass(frozen=True, slots=True)
class CandidateSolution:
    scenario_id: UUID
    values: Mapping[str, float]
    objective_value: float
    confidence: float
    solver_id: str

    def __post_init__(self):
        if not self.values:
            raise ContractValidationError("solution values must be non-empty")
        if not self.solver_id.strip():
            raise ContractValidationError("solver_id is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractValidationError("confidence must be between 0 and 1")


class SurrogateSolver(Protocol):
    def solve(self, request: SolverRequest) -> CandidateSolution: ...


class DeterministicBaselineSolver:
    """Reference solver; deliberately not coupled to a ML framework."""

    solver_id = "deterministic-baseline-v1"

    def solve(self, request: SolverRequest) -> CandidateSolution:
        target = request.constraints.get("target_position", 0.0)
        current = request.state.state.get("position", 0.0)
        error = target - current
        acceleration_limit = abs(request.constraints.get("max_acceleration", 1.0))
        acceleration = max(-acceleration_limit, min(acceleration_limit, error))
        return CandidateSolution(
            scenario_id=request.scenario_id,
            values={"acceleration": acceleration},
            objective_value=abs(error),
            confidence=1.0 if acceleration_limit > 0 else 0.0,
            solver_id=self.solver_id,
        )
