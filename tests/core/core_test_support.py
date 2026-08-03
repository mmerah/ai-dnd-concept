from pathlib import Path

from pydantic import BaseModel, SecretStr

from aidm.base import SAVE_VERSION, EngineId, Entity
from aidm.config import ProviderConfig, Providers, Roles, Settings
from aidm.content import Character, Scenario, authored_world
from aidm.engine import Engine
from aidm.engines.story.engine import build_story_engine
from aidm.store import load_character, load_scenario
from aidm.world import GameState, Record

REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
STORY = EngineId("story")
DND5E = EngineId("dnd5e")


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: GameState, entity: Entity) -> GameState:
    """Replace one entity, keeping whatever payload its record already holds."""
    world = state.world.model_copy(deep=True)
    world.records[entity.id] = Record(entity=entity, rules=world.record(entity.id).rules)
    return updated(state, world=world)


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", STORY)


def character() -> Character:
    return load_character(CHARACTERS, "kael", STORY)


def initialized() -> tuple[Engine, GameState]:
    selected_scenario = scenario()
    selected_character = character()
    engine = build_story_engine()
    authored = authored_world(selected_scenario, selected_character)
    state = GameState(
        save_version=SAVE_VERSION,
        scenario_id=selected_scenario.id,
        character_id=selected_character.id,
        scenario=selected_scenario.meta,
        engine=engine.id,
        world=engine.initial_world(authored, selected_character.overlay.character),
    )
    engine.validate_state(state)
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
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
    )
