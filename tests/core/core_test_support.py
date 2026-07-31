from pathlib import Path

from pydantic import SecretStr

from aidm.config import ProviderConfig, Providers, Roles, Settings
from aidm.domain.base import SAVE_VERSION
from aidm.domain.definitions import CharacterDefinition, ScenarioDefinition
from aidm.domain.state import GameState, attach_initial_rules, world_from_definitions
from aidm.store import read_character, read_scenario
from aidm_story.factory import StoryEngine, build_story_engine

REPOSITORY_ROOT = Path(__file__).parents[2]


def scenario() -> ScenarioDefinition:
    return read_scenario(REPOSITORY_ROOT / "scenarios" / "whispering_vault.json")


def character() -> CharacterDefinition:
    return read_character(REPOSITORY_ROOT / "characters" / "kael.json")


def initialized() -> tuple[StoryEngine, GameState]:
    selected_scenario = scenario()
    selected_character = character()
    engine = build_story_engine()
    world = world_from_definitions(selected_scenario, selected_character)
    initial = engine.lifecycle.initialise(world, selected_scenario, selected_character)
    state = GameState(
        save_version=SAVE_VERSION,
        engine=engine.id,
        scenario=selected_scenario.meta,
        world=attach_initial_rules(world, initial.entity_rules, engine.id),
        rules=initial.game_rules,
    )
    engine.rules.validate_state(state)
    return engine, state


def settings() -> Settings:
    return Settings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        roles=Roles(),
        max_growth=3,
        history_window=6,
        saves_dir=Path("saves"),
        scenarios_dir=Path("scenarios"),
        characters_dir=Path("characters"),
    )
