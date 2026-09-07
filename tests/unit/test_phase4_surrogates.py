from src.phase3_simulation.generators.scenarios import ScenarioGenerator
from src.phase4_surrogates.compilers.compiler import SurrogateCompiler
from src.phase4_surrogates.solvers.solver import DeterministicBaselineSolver, SolverRequest


def test_solver_preserves_identity():
    state = ScenarioGenerator().generate("tenant-a", "project-a", 5)
    request = SolverRequest(
        tenant_id="tenant-a",
        project_id="project-a",
        scenario_id=state.scenario_id,
        objective="reach target position",
        state=state,
        constraints={"target_position": 0.5, "max_acceleration": 1.0},
    )
    result = DeterministicBaselineSolver().solve(request)
    assert result.scenario_id == state.scenario_id
    assert result.values


def test_solver_rejects_cross_tenant_state():
    state = ScenarioGenerator().generate("tenant-a", "project-a", 5)
    try:
        SolverRequest(
            tenant_id="tenant-b",
            project_id="project-a",
            scenario_id=state.scenario_id,
            objective="reach target position",
            state=state,
            constraints={"target_position": 0.5},
        )
    except ValueError:
        return
    raise AssertionError("cross-tenant solver request was accepted")


def test_compiler_is_content_addressed_and_deterministic():
    compiler = SurrogateCompiler()
    first = compiler.compile({"acceleration": 0.25, "bias": 0.0})
    second = compiler.compile({"bias": 0.0, "acceleration": 0.25})
    assert first.artifact == second.artifact
    assert first.artifact_hash == second.artifact_hash


def test_compiled_surrogate_is_not_execution_authority():
    compiled = SurrogateCompiler().compile({"acceleration": 0.1})
    assert not hasattr(compiled, "lease")
    assert not hasattr(compiled, "capability")
    assert not hasattr(compiled, "authorization")
