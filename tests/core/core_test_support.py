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

from aidm.config import ProviderConfig, Providers, Settings
from aidm.content.io import load_character, load_scenario, read_scenarios
from aidm.content.model import Character, Scenario
from aidm.engines.core import (
    Engine,
    EntityRules,
    SheetBase,
    complete_chapter,
    player_action,
)
from aidm.engines.registry import ENGINES, begin_game, build_engines
from aidm.state.entities import EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact
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
ENGINE_IDS = tuple(ENGINES)
ENGINES_BUILT = build_engines(REPOSITORY_ROOT / "packs")


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: Game, entity: Entity) -> Game:
    draft = state.draft()
    draft.world.entities[entity.id] = entity
    return draft.committed()


def at_boundary[S: SheetBase](state: Game, sheet_type: type[S]) -> Game:
    """One chapter recorded — an adventure ended, a job done — for everyone who played it."""
    draft = state.draft()
    _ = complete_chapter(draft, "a chapter closed", sheet_type)
    return draft.committed()


def sheet_of[R: EntityRules](state: Game, entity_id: EntityId, model: type[R]) -> R:
    """One entity's rules as its engine parses them: a copy, so changing state needs `rules()`."""
    return model.model_validate(state.world.require(entity_id).rules)


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault")


def character() -> Character:
    engine = ENGINES_BUILT[LONER3E]
    return load_character(CHARACTERS, "kael", engine.id, engine.check_overlay)


def scenario_for(engine_id: EngineId) -> Slug:
    """Read off the shipped content rather than tabulated, so a second one fails here loudly."""
    shipped = [
        slug
        for slug, scenario in read_scenarios(SCENARIOS, ENGINE_IDS)
        if scenario.engine == engine_id
    ]
    if len(shipped) != 1:
        raise ValueError(f"{engine_id!r} ships {len(shipped)} scenarios, not one: {shipped}")
    return shipped[0]


def game(engine_id: EngineId) -> tuple[Engine, Game]:
    """The scenario authored for this engine and the shipped character, composed together."""
    engine = ENGINES_BUILT[engine_id]
    scenario_id = scenario_for(engine_id)
    selected_scenario = load_scenario(SCENARIOS, scenario_id)
    selected_character = load_character(CHARACTERS, "kael", engine.id, engine.check_overlay)
    return engine, begin_game(engine, scenario_id, selected_scenario, selected_character)


def initialized() -> tuple[Engine, Game]:
    return game(LONER3E)


def structured(**output: object) -> ModelResponse:
    return ModelResponse(parts=[TextPart(json.dumps(output))])


def tool_call(tool: str, **args: object) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=json.dumps(args))])


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
    settings: Settings | None = None,
) -> TurnResult:
    """Build a session-style turn with every model role stubbed."""
    settings = settings or offline_settings()
    stages = build_turn_agents(engine, settings)
    narrator = narrator or FunctionModel(scripted(narrated("You wait.")))
    with ExitStack() as stack:
        stack.enter_context(stages.director.override(model=director))
        stack.enter_context(stages.narrator.override(model=narrator))
        return await run_segment(
            state,
            player_input,
            engine=engine,
            stages=stages,
            settings=settings,
            rng=Random(0) if rng is None else rng,
            on_step=on_step,
            on_event=on_event,
        )


def offline_settings() -> Settings:
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


class Breath(Frozen):
    deep: bool


def _breathe(draft: Game, args: Breath) -> list[Fact]:
    del draft
    return [
        Fact(kind="breathed", trace="Kael breathes deep", told=args.deep),
        Fact(kind="breathed", trace="the hidden stair creaks", told=False),
    ]


CATCH_BREATH = player_action(
    "catch-breath",
    "A moment to recover.",
    Breath,
    _breathe,
    lambda state: (("Catch your breath", Breath(deep=True)),),
)
