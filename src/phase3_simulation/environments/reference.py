from ..contracts import SimulationAction, SimulationResult, SimulationState


class DeterministicReferenceEnvironment:
    """Minimal deterministic environment used to validate simulation semantics."""

    def reset(self, state: SimulationState) -> SimulationState:
        return state

    def step(self, state: SimulationState, action: SimulationAction) -> SimulationResult:
        position = state.state["position"]
        velocity = state.state["velocity"]
        acceleration = float(action.parameters.get("acceleration", 0.0))
        next_velocity = velocity + acceleration
        next_position = position + next_velocity
        next_state = SimulationState(
            tenant_id=state.tenant_id,
            project_id=state.project_id,
            scenario_id=state.scenario_id,
            environment_id=state.environment_id,
            step=state.step + 1,
            state={"position": next_position, "velocity": next_velocity},
            seed=state.seed,
        )
        target = float(action.parameters.get("target_position", 0.0))
        error = abs(next_position - target)
        return SimulationResult(
            previous=state,
            next_state=next_state,
            reward=-error,
            terminated=error < 0.01,
            diagnostics={"position_error": error, "velocity": next_velocity},
        )

    def evaluate(self, state: SimulationState, actions: list[SimulationAction]) -> list[SimulationResult]:
        current = state
        results: list[SimulationResult] = []
        for action in actions:
            result = self.step(current, action)
            results.append(result)
            current = result.next_state
            if result.terminated:
                break
        return results
