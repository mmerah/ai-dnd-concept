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
from aidm.engines.loader import Engine, Subsystem
from aidm.state.base import EngineId, Entity
from aidm.state.turn import Turn
from aidm.state.world import GameState
from aidm.turn.pipeline import TurnResult, run_turn
from aidm.turn.roles import build_stages

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]

REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
LONER3E = EngineId("loner3e")
TWENTYFOURXX = EngineId("twentyfourxx")
CAIRN2E = EngineId("cairn2e")


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: GameState, entity: Entity) -> GameState:
    draft = state.draft()
    draft.world.entities[entity.id] = entity
    return draft.committed()


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", build_engine(LONER3E).binding())


def character() -> Character:
    return load_character(CHARACTERS, "kael", build_engine(LONER3E).binding())


def game(engine_id: EngineId) -> tuple[Engine, GameState]:
    """The shipped scenario and character, composed under one engine."""
    engine = build_engine(engine_id)
    binding = engine.binding()
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault", binding)
    selected_character = load_character(CHARACTERS, "kael", binding)
    return engine, begin_game(engine, selected_scenario, selected_character)


def initialized() -> tuple[Engine, GameState]:
    return game(LONER3E)


def capability(engine: Engine) -> Subsystem:
    """The shipped engine grows its characters; a test that asks for the capability wants it."""
    return engine.subsystems[0]


def structured(**output: object) -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps(output))])


def call(name: str, **args: object) -> dict[str, object]:
    """One wire call: the vocabulary name, and what it is named with."""
    return {"name": name, "args": args}


def plan(**output: object) -> ModelResponse:
    """The director answers by calling the plan tool, as ToolOutput presents it."""
    args = json.dumps({"focus": "Kael acts.", "effects": [], **output})
    return ModelResponse(parts=[ToolCallPart(tool_name="turn_plan", args=args)])


def beat(**output: object) -> ModelResponse:
    """The same role asked again once the dice have settled: the plan's shape without framing."""
    args = json.dumps({"effects": [], **output})
    return ModelResponse(parts=[ToolCallPart(tool_name="turn_beat", args=args)])


def ends_the_turn() -> Stub:
    """The continuation a turn gets when a test is not about the loop: it adds nothing."""
    quiet = beat()

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return quiet

    return stub


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
    beats: Model | None = None,
    settle: Model | None = None,
    narrator: Model | None = None,
    worldkeeper: Model | None = None,
    rng: Random | None = None,
    on_step: Callable[[str], None] | None = None,
) -> TurnResult:
    """The turn with every role stubbed, built the way the session builds it."""
    config = settings()
    stages = build_stages(engine, config)
    roles = (stages.director, stages.beat, stages.settle, stages.narrator, stages.worldkeeper)
    models = (
        director,
        beats or FunctionModel(ends_the_turn()),
        settle or FunctionModel(ends_the_turn()),
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
            settings=config,
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
