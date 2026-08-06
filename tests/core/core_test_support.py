import json
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, SecretStr
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo

from aidm.core.base import SAVE_VERSION, EngineId, Entity
from aidm.core.config import ProviderConfig, Providers, Settings
from aidm.core.content import Character, Scenario, authored_world
from aidm.core.engine import Engine
from aidm.core.registry import build_engine
from aidm.core.store import load_character, load_scenario
from aidm.core.world import GameState

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]

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
    draft = state.draft()
    draft.world.record(entity.id).entity = entity
    return draft.committed()


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", STORY)


def character() -> Character:
    return load_character(CHARACTERS, "kael", STORY)


def game(engine_id: EngineId) -> tuple[Engine, GameState]:
    """The shipped scenario and character, composed under one engine."""
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault", engine_id)
    selected_character = load_character(CHARACTERS, "kael", engine_id)
    engine = build_engine(engine_id, settings())
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


def initialized() -> tuple[Engine, GameState]:
    return game(STORY)


def structured(**output: object) -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps(output))])


def plan(**output: object) -> ModelResponse:
    """The director answers by calling the plan tool, as ToolOutput presents it."""
    return ModelResponse(parts=[ToolCallPart(tool_name="turn_plan", args=json.dumps(output))])


def text(body: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(body)])


def scripted(*responses: ModelResponse) -> Stub:
    """Call N answers with response N, because a retried output asks the model again."""
    remaining = iter(responses)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return next(remaining)

    return stub


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
