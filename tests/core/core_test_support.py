from pathlib import Path
from random import Random

from pydantic import BaseModel, SecretStr
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from aidm.kernel.base import SAVE_VERSION, EngineId, Entity
from aidm.kernel.config import ProviderConfig, Providers, Roles, Settings
from aidm.kernel.content import Character, Scenario, authored_world
from aidm.kernel.engine import Engine
from aidm.kernel.store import load_character, load_scenario
from aidm.kernel.world import GameState, Record
from aidm.plugins.story.engine import build_story_engine
from aidm.workflow.tools import TurnContext

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


def turn_context(engine: Engine, state: GameState, rng: Random | None = None) -> TurnContext:
    return TurnContext(
        draft=state.draft(),
        rng=Random(0) if rng is None else rng,
        facts=[],
        default_rules=engine.default_rules,
    )


def tool_context(deps: TurnContext) -> RunContext[TurnContext]:
    """Tools take a `RunContext`; a test builds one instead of running an agent."""
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


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
