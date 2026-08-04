from pathlib import Path
from random import Random

from pydantic import BaseModel, SecretStr
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from aidm.core.base import SAVE_VERSION, EngineId, Entity
from aidm.core.config import ProviderConfig, Providers, Settings
from aidm.core.content import Character, Scenario, authored_world
from aidm.core.engine import Engine
from aidm.core.registry import AnyEngine, build_engine
from aidm.core.store import load_character, load_scenario
from aidm.core.tools import TurnContext
from aidm.core.world import EngineRules, GameState

REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
STORY = EngineId("story")
DND5E = EngineId("dnd5e")


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity[R: EngineRules](state: GameState[R], entity: Entity) -> GameState[R]:
    """Replace one entity, keeping whatever payload its record already holds."""
    draft = state.draft()
    draft.world.record(entity.id).entity = entity
    return draft.committed()


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", STORY)


def character() -> Character:
    return load_character(CHARACTERS, "kael", STORY)


def initialized() -> tuple[AnyEngine, GameState[EngineRules]]:
    selected_scenario = scenario()
    selected_character = character()
    engine = build_engine(STORY, settings())
    authored = authored_world(selected_scenario, selected_character)
    state = engine.state_type(
        save_version=SAVE_VERSION,
        scenario_id=selected_scenario.id,
        character_id=selected_character.id,
        scenario=selected_scenario.meta,
        engine=engine.id,
        world=engine.initial_world(authored, selected_character.overlay.character),
    )
    engine.validate_state(state)
    return engine, state


def turn_context[R: EngineRules](
    engine: Engine[R], state: GameState[R], rng: Random | None = None
) -> TurnContext[R]:
    return TurnContext(
        draft=state.draft(),
        rng=Random(0) if rng is None else rng,
        facts=[],
        default_rules=engine.default_rules,
    )


def tool_context[R: EngineRules](deps: TurnContext[R]) -> RunContext[TurnContext[R]]:
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
        max_growth=3,
        history_window=6,
        saves_dir=Path("saves"),
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
    )
