import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from random import Random

from pydantic import BaseModel, JsonValue
from pydantic_settings import SettingsConfigDict

from aidm.app import mcp
from aidm.app.launch import LaunchTarget
from aidm.app.runtime import GameService, Runtime
from aidm.app.spawn import RunResult
from aidm.config import Role, Settings
from aidm.core.entities import EngineId, EntityId, Slug
from aidm.core.facts import Fact
from aidm.core.io import load_character, read_scenario, read_scenarios
from aidm.core.model import AnyGame
from aidm.core.play import Answer, Speaker
from aidm.core.tools import NoArgs
from aidm.engines.core import PLAYER_ID, AnyEngine
from aidm.engines.loner3e.tools import complete_chapter as loner_chapter
from aidm.engines.loner3e.world import (
    Loner3eCharacterFile,
    Loner3eGame,
    Loner3eScenarioFile,
    LonerCharacter,
)
from aidm.engines.registry import begin_game, build_engines
from aidm.turn.run import TurnStep

# One tool call as a scripted game master makes it.
type Call = tuple[str, dict[str, JsonValue]]


class EnvFileFreeSettings(Settings):
    """The checkout's .env must not leak into tests; monkeypatched env vars still apply."""

    model_config = SettingsConfigDict(env_file=None)


REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
LONER3E = EngineId("loner3e")
TUNNELGOONS = EngineId("tunnelgoons")
ENGINES_BUILT = build_engines(REPOSITORY_ROOT / "packs")
ENGINE_IDS = tuple(ENGINES_BUILT)
SCENARIO_MODELS = {engine_id: engine.scenario for engine_id, engine in ENGINES_BUILT.items()}
KAEL = Speaker(name="Kael", id=PLAYER_ID)


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: Loner3eGame, entity: LonerCharacter) -> Loner3eGame:
    """Added to the cast and to the scene: present must be known, so an unmet one is hidden."""
    draft = state.draft()
    draft.payload.world.cast[entity.id] = entity
    run = draft.payload.world.run
    (run.present if entity.known else run.hidden).append(entity.id)
    return draft.committed()


def loner_at_boundary(state: Loner3eGame) -> Loner3eGame:
    draft = state.draft()
    _ = loner_chapter(draft, NoArgs(), Random(0))
    return draft.committed()


def loner_sheet(state: Loner3eGame, entity_id: EntityId) -> LonerCharacter:
    return state.payload.world.require(entity_id)


def scenario() -> Loner3eScenarioFile:
    loaded = read_scenario(SCENARIOS, "whispering-vault", SCENARIO_MODELS)
    if not isinstance(loaded, Loner3eScenarioFile):
        raise AssertionError("the Loner scenario parsed as another engine")
    return loaded


def character() -> Loner3eCharacterFile:
    engine = ENGINES_BUILT[LONER3E]
    loaded = load_character(CHARACTERS, "kael", engine.id, engine.character)
    if not isinstance(loaded, Loner3eCharacterFile):
        raise AssertionError("the Loner character parsed as another engine")
    return loaded


def scenario_for(engine_id: EngineId) -> Slug:
    """Read off the shipped content rather than tabulated, so a second one fails here loudly."""
    shipped = [
        slug
        for slug, scenario in read_scenarios(SCENARIOS, SCENARIO_MODELS)
        if scenario.engine == engine_id
    ]
    if len(shipped) != 1:
        raise ValueError(f"{engine_id!r} ships {len(shipped)} scenarios, not one: {shipped}")
    return shipped[0]


def game(engine_id: EngineId) -> tuple[AnyEngine, AnyGame]:
    """The scenario authored for this engine and the shipped character, composed together."""
    engine = ENGINES_BUILT[engine_id]
    scenario_id = scenario_for(engine_id)
    selected_scenario = read_scenario(SCENARIOS, scenario_id, SCENARIO_MODELS)
    selected_character = load_character(CHARACTERS, "kael", engine.id, engine.character)
    begun = begin_game(engine, scenario_id, selected_scenario, selected_character)
    return engine, begun


def initialized() -> tuple[AnyEngine, Loner3eGame]:
    engine, state = game(LONER3E)
    if not isinstance(state, Loner3eGame):
        raise AssertionError("the Loner engine began another game type")
    return engine, state


def change_args(verb: str, **fields: JsonValue) -> dict[str, JsonValue]:
    return {"change": {"verb": verb, **fields}}


def changed(verb: str, **fields: JsonValue) -> Call:
    return "change_world", change_args(verb, **fields)


def tool_call(name: str, **args: JsonValue) -> Call:
    return name, args


def the_way_on() -> Call:
    return "next_scene", {}


def narrated(body: str, speaker_id: str | None = None) -> str:
    return json.dumps({"lines": [{"speaker_id": speaker_id, "text": body}]})


def offline_settings(saves: Path | None = None) -> Settings:
    return EnvFileFreeSettings(
        saves_dir=Path("saves") if saves is None else saves,
        scenarios_dir=SCENARIOS,
        characters_dir=CHARACTERS,
    )


@dataclass(slots=True)
class ScriptedSpawner:
    """Answers from a per-role list and records every prompt it was given. Tests use this."""

    turns: list[Callable[[], None]] = field(default_factory=list)
    answers: dict[Role, list[str]] = field(default_factory=dict)
    prompts: list[tuple[Role, str]] = field(default_factory=list)
    resumed: list[tuple[Role, str | None]] = field(default_factory=list)

    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult:
        self.prompts.append((role, prompt))
        self.resumed.append((role, session))
        # A session every time, so a test exercises the resumed path the real CLIs take.
        spoke = partial(RunResult, session=f"{role}-1")
        if role == "master":
            if self.turns:
                self.turns.pop(0)()
            return spoke(prompt)
        answers = self.answers.get(role)
        if not answers:
            raise ValueError(f"the scripted {role} has no answer left")
        return spoke(answers.pop(0))

    def prompt(self, role: Role) -> str:
        """The first prompt the role was given; the golden prompts come from here."""
        return next(text for name, text in self.prompts if name == role)


@dataclass(slots=True)
class Table[G: AnyGame]:
    """A live game and the tool surface a scripted game master plays it through."""

    runtime: Runtime
    service: GameService
    spawner: ScriptedSpawner
    state_type: type[G]
    refusals: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)

    def call(self, name: str, args: dict[str, JsonValue]) -> str:
        """What the server does: a refusal is an error result the CLI reads and carries on from."""
        try:
            answered = mcp.call(self.runtime, name, args)
        except ValueError as refused:
            self.refusals.append(str(refused))
            answered = str(refused)
        self.answers.append(answered)
        return answered

    def plays(self, calls: Sequence[Call], *, start: bool = True) -> Callable[[], None]:
        def run() -> None:
            for name, args in (("start_turn", {}), *calls) if start else calls:
                _ = self.call(name, args)

        return run

    @property
    def state(self) -> G:
        state = self.service.state
        if not isinstance(state, self.state_type):
            raise AssertionError(f"the service holds an unexpected {self.state_type.__name__}")
        return state

    def saved(self) -> G:
        raw = self.service.store.load(self.service.slug)
        assert raw is not None
        restored = self.service.engine.restored(raw)
        if not isinstance(restored, self.state_type):
            raise AssertionError(f"the save restored an unexpected {self.state_type.__name__}")
        return restored


def opened(
    saves: Path,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
    engine: AnyEngine | None = None,
) -> Table[Loner3eGame]:
    return _opened(
        saves,
        rng=rng,
        settings=settings,
        engine=engine,
        engine_id=LONER3E,
        state_type=Loner3eGame,
    )


def opened_for(
    saves: Path,
    engine_id: EngineId,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
) -> Table[AnyGame]:
    """Open a golden-test table for whichever concrete engine is under test."""
    engine = ENGINES_BUILT[engine_id]
    return _opened(
        saves,
        rng=rng,
        settings=settings,
        engine=engine,
        engine_id=engine_id,
        state_type=engine.game,
    )


def _opened[G: AnyGame](
    saves: Path,
    *,
    rng: Random | None,
    settings: Settings | None,
    engine: AnyEngine | None,
    engine_id: EngineId,
    state_type: type[G],
) -> Table[G]:
    settings = settings or offline_settings(saves)
    spawner = ScriptedSpawner()
    runtime = Runtime(settings, spawner)
    selected_engine = ENGINES_BUILT[engine_id] if engine is None else engine
    runtime.engines[engine_id] = selected_engine
    scenario_id = scenario_for(engine_id)
    service = runtime.session(
        LaunchTarget(slug=f"{scenario_id}--kael", scenario_id=scenario_id, character_id="kael")
    )
    if rng is not None:
        service.rng = rng
    return Table(runtime=runtime, service=service, spawner=spawner, state_type=state_type)


async def played[G: AnyGame](
    table: Table[G],
    action: str | Answer,
    *calls: Call,
    narration: str = "You wait.",
    arrival: str | None = None,
    start: bool = True,
    moving_on: bool = False,
    on_step: Callable[[TurnStep], None] | None = None,
    on_fact: Callable[[Fact], None] | None = None,
) -> G:
    """One turn, with the game master's tool calls scripted and the narrator's answer canned."""
    table.spawner.turns.append(table.plays(calls, start=start))
    canned = table.spawner.answers.setdefault("narrator", [])
    canned.append(narrated(narration))
    # The crossing is its own narrator spawn, so a turn that installs a scene answers twice.
    if arrival is not None:
        canned.append(narrated(arrival))
    await table.service.play(action, on_step=on_step, on_fact=on_fact, moving_on=moving_on)
    return table.state
