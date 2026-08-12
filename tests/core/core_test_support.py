import json
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from random import Random

from pydantic import BaseModel, JsonValue, SecretStr
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aidm.app.session import begin_game, build_engine
from aidm.config import ProviderConfig, Providers, Settings
from aidm.content.authored import Character, Scenario
from aidm.content.store import load_character, load_scenario
from aidm.engines.loader import Advancement, Engine
from aidm.state.base import EngineId, Entity
from aidm.state.turn import Turn
from aidm.state.world import GameState
from aidm.turn.pipeline import TurnResult, run_turn
from aidm.turn.roles import build_stages

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]

REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
STORY = EngineId("story")


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: GameState, entity: Entity) -> GameState:
    draft = state.draft()
    draft.world.entities[entity.id] = entity
    return draft.committed()


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", STORY)


def character() -> Character:
    return load_character(CHARACTERS, "kael", STORY)


def game(engine_id: EngineId) -> tuple[Engine, GameState]:
    """The shipped scenario and character, composed under one engine."""
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault", engine_id)
    selected_character = load_character(CHARACTERS, "kael", engine_id)
    engine = build_engine(engine_id)
    return engine, begin_game(engine, selected_scenario, selected_character)


def initialized() -> tuple[Engine, GameState]:
    return game(STORY)


def capability(engine: Engine) -> Advancement:
    """The shipped engine grows its characters; a test that asks for the capability wants it."""
    found = engine.advancement
    assert found is not None
    return found


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


def shown(turn: Turn, name: str) -> str:
    return next(step.prompt or "" for step in turn.steps if step.name == name)


def answered(turn: Turn, name: str) -> dict[str, JsonValue]:
    output = next(step.output for step in turn.steps if step.name == name)
    if not isinstance(output, dict):
        raise TypeError(f"step {name!r} answered {type(output).__name__}, not a structured output")
    return output


async def played(
    engine: Engine,
    state: GameState,
    prompt: str,
    *,
    director: Model,
    narrator: Model | None = None,
    worldkeeper: Model | None = None,
    scene: Model | None = None,
    rng: Random | None = None,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    """The turn with every role stubbed, built the way the session builds it."""
    stages = build_stages(engine, settings())
    roles = (stages.scene, stages.director, stages.narrator, stages.worldkeeper)
    models = (
        scene or FunctionModel(scripted(structured(focus="Kael acts."))),
        director,
        narrator or FunctionModel(scripted(text("You wait."))),
        worldkeeper or FunctionModel(scripted(structured(creations=[]))),
    )
    with ExitStack() as stack:
        for role, model in zip(roles, models, strict=True):
            stack.enter_context(role.agent.override(model=model))
        return await run_turn(
            state,
            prompt,
            engine=engine,
            stages=stages,
            history_window=6,
            max_growth=3,
            max_memories=2,
            rng=Random(0) if rng is None else rng,
            on_step=on_step,
        )


def settings() -> Settings:
    return Settings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        max_growth=3,
        max_memories=2,
        history_window=6,
        saves_dir=Path("saves"),
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
    )
