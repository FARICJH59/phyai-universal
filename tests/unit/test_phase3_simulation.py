from src.phase3_simulation.contracts import SimulationAction
from src.phase3_simulation.environments.reference import DeterministicReferenceEnvironment
from src.phase3_simulation.generators.scenarios import ScenarioGenerator


def test_scenario_generation_is_deterministic():
    generator = ScenarioGenerator()
    first = generator.generate("tenant-a", "project-a", 42)
    second = generator.generate("tenant-a", "project-a", 42)
    assert first == second


def test_scenario_identity_isolation():
    generator = ScenarioGenerator()
    first = generator.generate("tenant-a", "project-a", 42)
    second = generator.generate("tenant-b", "project-a", 42)
    assert first.scenario_id != second.scenario_id


def test_reference_environment_is_deterministic():
    generator = ScenarioGenerator()
    state = generator.generate("tenant-a", "project-a", 7)
    action = SimulationAction("plant", "move", {"acceleration": 0.1, "target_position": 0.5})
    env = DeterministicReferenceEnvironment()
    assert env.step(state, action) == env.step(state, action)


def test_simulation_preserves_tenant_and_project():
    state = ScenarioGenerator().generate("tenant-a", "project-a", 1)
    result = DeterministicReferenceEnvironment().step(
        state, SimulationAction("plant", "move", {"acceleration": 0.0})
    )
    assert result.next_state.tenant_id == "tenant-a"
    assert result.next_state.project_id == "project-a"
    assert result.next_state.step == 1


def test_simulation_action_has_no_authority_fields():
    action = SimulationAction("plant", "move", {"acceleration": 0.0})
    assert not hasattr(action, "lease")
    assert not hasattr(action, "capability")
    assert not hasattr(action, "authorization")
