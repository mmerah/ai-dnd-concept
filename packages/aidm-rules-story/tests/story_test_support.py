from pathlib import Path

from aidm.domain.state import GameState, attach_initial_rules, world_from_definitions
from aidm.store import read_character, read_scenario
from aidm_story.direction import Risk, StoryConsequence, StoryDirection, TakeStress
from aidm_story.engine import StoryEngine, create_story_engine

REPOSITORY_ROOT = Path(__file__).parents[3]


def initial_story_game() -> tuple[StoryEngine, GameState]:
    scenario = read_scenario(REPOSITORY_ROOT / "scenarios" / "whispering_vault.json")
    character = read_character(REPOSITORY_ROOT / "characters" / "kael.json")
    engine = create_story_engine()
    world = world_from_definitions(scenario, character)
    initialized = engine.lifecycle.initialise(world, scenario, character)
    state = GameState(
        engine=engine.stamp,
        scenario=scenario.meta,
        world=attach_initial_rules(world, initialized.entity_rules, engine.stamp),
        rules=initialized.game_rules,
    )
    engine.rules.validate_state(state)
    return engine, state


def setback_direction(*, take_stress: bool = False) -> StoryDirection:
    branch: list[StoryConsequence] = [TakeStress(amount=1)] if take_stress else []
    risk = Risk(
        approach="empathetic",
        difficulty=2,
        on_setback=branch,
    )
    mechanics: list[StoryConsequence] = [risk]
    return StoryDirection(
        intent="Kael attempts something dangerous.",
        tone="tense",
        mechanics=mechanics,
    )
