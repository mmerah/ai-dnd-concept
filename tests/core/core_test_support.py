import json
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from pydantic import BaseModel, SecretStr
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_settings import SettingsConfigDict

from aidm.app.launch import begin_game, build_engine
from aidm.config import ProviderConfig, Providers, Settings
from aidm.content.io import load_character, load_scenario
from aidm.content.model import Character, Scenario
from aidm.engines.core import Advancement, Engine, SheetMechanics
from aidm.state.entities import EngineId, Entity
from aidm.state.model import Game
from aidm.state.play import Answer, MechanicEvent, TurnTrace
from aidm.turn.run import TurnResult, TurnStep, build_turn_agents, run_segment

type Stub = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


class EnvFileFreeSettings(Settings):
    """The checkout's .env must not leak into tests; monkeypatched env vars still apply."""

    model_config = SettingsConfigDict(env_file=None)


REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
LONER3E = EngineId("loner3e")
TWENTYFOURXX = EngineId("twentyfourxx")


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: Game, entity: Entity) -> Game:
    draft = state.draft()
    entities = draft.world.entities
    held = draft.world.find(entity.id)
    if held is None:
        entities.append(entity)
    else:
        entities[entities.index(held)] = entity
    return draft.committed()


def at_boundary(state: Game) -> Game:
    """One boundary recorded — an adventure ended, a job done — the trigger both engines count."""
    draft = state.draft()
    SheetMechanics.of_game(draft).completed.current = 1
    return draft.committed()


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault")


def character() -> Character:
    engine = build_engine(LONER3E)
    return load_character(CHARACTERS, "kael", engine.id, engine.check_overlay)


def game(engine_id: EngineId) -> tuple[Engine, Game]:
    """The shipped scenario and character, composed under one engine."""
    engine = build_engine(engine_id)
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault")
    selected_character = load_character(CHARACTERS, "kael", engine.id, engine.check_overlay)
    return engine, begin_game(engine, "whispering-vault", selected_scenario, selected_character)


def initialized() -> tuple[Engine, Game]:
    return game(LONER3E)


def capability(engine: Engine) -> Advancement:
    """The shipped engine grows its characters; a test that asks for the capability wants it."""
    assert engine.advancement is not None
    return engine.advancement


def structured(**output: object) -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps(output))])


def tool_call(name: str, **args: object) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=name, args=json.dumps(args))])


def text(body: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(body)])


def narrated(body: str) -> ModelResponse:
    """The narrator's answer, as `NativeOutput(Narration)` presents it."""
    return structured(lines=[{"speaker_id": None, "text": body}])


def scripted(*responses: ModelResponse) -> Stub:
    """Call N answers with response N, because a retried output asks the model again."""
    remaining = iter(responses)

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return next(remaining)

    return stub


@dataclass(slots=True)
class Recorder:
    """A scripted stub that keeps what it was asked, so a test can read the retries it was sent."""

    stub: Stub
    calls: list[list[ModelMessage]] = field(default_factory=list)

    def reasons(self) -> list[str]:
        return [
            str(part.content)
            for messages in self.calls
            for part in messages[-1].parts
            if isinstance(part, RetryPromptPart)
        ]


def recorded(*responses: ModelResponse) -> Recorder:
    answer = scripted(*responses)
    calls: list[list[ModelMessage]] = []

    def stub(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(list(messages))
        return answer(messages, info)

    return Recorder(stub=stub, calls=calls)


def shown(turn: TurnTrace, name: str) -> str:
    return next(step.prompt for step in turn.steps if step.name == name)


async def played(
    engine: Engine,
    state: Game,
    player_input: str | Answer,
    *,
    director: Model,
    narrator: Model | None = None,
    rng: Random | None = None,
    on_step: Callable[[TurnStep], None] | None = None,
    on_event: Callable[[MechanicEvent], None] | None = None,
    config: Settings | None = None,
) -> TurnResult:
    """Build a session-style turn with every model role stubbed."""
    config = config or settings()
    stages = build_turn_agents(engine, config)
    narrator = narrator or FunctionModel(scripted(narrated("You wait.")))
    with ExitStack() as stack:
        stack.enter_context(stages.director.override(model=director))
        stack.enter_context(stages.narrator.override(model=narrator))
        return await run_segment(
            state,
            player_input,
            engine=engine,
            stages=stages,
            settings=config,
            rng=Random(0) if rng is None else rng,
            on_step=on_step,
            on_event=on_event,
        )


def settings() -> Settings:
    return EnvFileFreeSettings(
        providers=Providers(
            openrouter=ProviderConfig(
                base_url="https://example.invalid/v1",
                api_key=SecretStr("test"),
            )
        ),
        saves_dir=Path("saves"),
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
    )
