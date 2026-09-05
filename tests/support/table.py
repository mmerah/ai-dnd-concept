import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from random import Random

import pytest
from pydantic import BaseModel, JsonValue
from pydantic_settings import SettingsConfigDict

from aidm.app import mcp
from aidm.app.launch import LaunchTarget
from aidm.app.runtime import GameService, Runtime
from aidm.app.spawn import RunResult
from aidm.config import Role, Settings
from aidm.core.entities import EngineId, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.io import Library, decode
from aidm.core.model import AnyGame
from aidm.core.play import Answer
from aidm.engines.registry import build_engines
from aidm.engines.seam import AnyEngine

# One tool call as a scripted game master makes it.
type Call = tuple[str, dict[str, JsonValue]]


class EnvFileFreeSettings(Settings):
    """The checkout's .env must not leak into tests; monkeypatched env vars still apply."""

    model_config = SettingsConfigDict(env_file=None)


REPOSITORY_ROOT = Path(__file__).parents[2]
SCENARIOS = REPOSITORY_ROOT / "scenarios"
CHARACTERS = REPOSITORY_ROOT / "characters"
LIBRARY = Library(SCENARIOS, CHARACTERS)
LONER3E = EngineId("loner3e")
TUNNELGOONS = EngineId("tunnelgoons")
BREATHLESS = EngineId("breathless")
TWENTYFOURXX = EngineId("twentyfourxx")
ENGINES_BUILT = build_engines()
ENGINE_IDS = tuple(ENGINES_BUILT)
SCENARIO_MODELS = {engine_id: engine.scenario for engine_id, engine in ENGINES_BUILT.items()}


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def scenario_for(engine_id: EngineId) -> Slug:
    """Read off the shipped content rather than tabulated, so a second one fails here loudly."""
    matches = [
        slug
        for slug, scenario in LIBRARY.read_scenarios(SCENARIO_MODELS)
        if scenario.engine == engine_id
    ]
    if len(matches) != 1:
        raise ValueError(f"{engine_id!r} ships {len(matches)} scenarios, not one: {matches}")
    return matches[0]


def game(engine_id: EngineId) -> tuple[AnyEngine, AnyGame]:
    """The scenario authored for this engine and the shipped character, composed together."""
    engine = ENGINES_BUILT[engine_id]
    scenario_id = scenario_for(engine_id)
    selected_scenario = LIBRARY.read_scenario(scenario_id, SCENARIO_MODELS)
    selected_character = LIBRARY.read_character("kael", engine.id, engine.character)
    begun = engine.begin(scenario_id, selected_scenario, selected_character)
    return engine, begun


def change_args(verb: str, **fields: JsonValue) -> dict[str, JsonValue]:
    return {"change": {"verb": verb, **fields}}


def changed(verb: str, **fields: JsonValue) -> Call:
    return "change_world", change_args(verb, **fields)


def change(engine: AnyEngine, draft: AnyGame, verb: str, **fields: JsonValue) -> list[Fact]:
    return list(engine.tools["change_world"].call(draft, change_args(verb, **fields), Random(0)))


def refused(engine: AnyEngine, draft: AnyGame, verb: str, **fields: JsonValue) -> str:
    """The refusal's text, from `pytest.raises(Refusal)`."""
    with pytest.raises(Refusal) as raised:
        _ = change(engine, draft, verb, **fields)
    return str(raised.value)


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
            raise Refusal(f"the scripted {role} has no answer left")
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
    facts: list[Fact] = field(default_factory=list)

    def call(self, name: str, args: dict[str, JsonValue]) -> str:
        """What the server does: a refusal is an error result the CLI reads and carries on from."""
        try:
            answered = mcp.call(self.runtime, name, args)
        except Refusal as refused:
            self.refusals.append(str(refused))
            answered = str(refused)
        self.answers.append(answered)
        return answered

    def plays(self, calls: Sequence[Call]) -> Callable[[], None]:
        def run() -> None:
            for name, args in calls:
                _ = self.call(name, args)
            # Snapshotted here: the service drops the turn once it is filed.
            if (turn := self.service.turn) is not None:
                self.facts = list(turn.facts)

        return run

    @property
    def state(self) -> G:
        state = self.service.state
        assert isinstance(state, self.state_type), (
            f"the service holds an unexpected {self.state_type.__name__}"
        )
        return state

    def saved(self) -> G:
        raw = self.service.store.load(self.service.slug)
        assert raw is not None
        restored = self.service.engine.restore(decode(raw))
        assert isinstance(restored, self.state_type), (
            f"the save restored an unexpected {self.state_type.__name__}"
        )
        return restored


def open_game_for(
    saves: Path,
    engine_id: EngineId,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
) -> Table[AnyGame]:
    """Open a golden-test table for whichever concrete engine is under test."""
    return open_table(
        saves,
        rng=rng,
        settings=settings,
        engine_id=engine_id,
        state_type=ENGINES_BUILT[engine_id].game,
    )


def open_table[G: AnyGame](
    saves: Path,
    *,
    engine_id: EngineId,
    state_type: type[G],
    rng: Random | None = None,
    settings: Settings | None = None,
    engine: AnyEngine | None = None,
) -> Table[G]:
    settings = settings or offline_settings(saves)
    spawner = ScriptedSpawner()
    runtime = Runtime(settings, spawner)
    selected_engine = ENGINES_BUILT[engine_id] if engine is None else engine
    runtime.engines[engine_id] = selected_engine
    scenario_id = scenario_for(engine_id)
    service = runtime.session(LaunchTarget(scenario_id=scenario_id, character_id="kael"))
    if rng is not None:
        service.rng = rng
    return Table(runtime=runtime, service=service, spawner=spawner, state_type=state_type)


async def play_turn[G: AnyGame](
    table: Table[G],
    prompt: str | Answer,
    *calls: Call,
    narration: str = "You wait.",
    arrival: str | None = None,
    action: Slug | None = None,
) -> G:
    """One turn, with the game master's tool calls scripted and the narrator's answer canned;
    `action` is the page's own way of opening it."""
    table.spawner.turns.append(table.plays(calls))
    canned = table.spawner.answers.setdefault("narrator", [])
    canned.append(narrated(narration))
    # The arrival is its own narrator spawn, so a turn that installs a scene answers twice.
    if arrival is not None:
        canned.append(narrated(arrival))
    if action is not None:
        assert isinstance(prompt, str)
        await table.service.act(action, prompt)
    else:
        await table.service.play(Answer(text=prompt) if isinstance(prompt, str) else prompt)
    return table.state


async def take[G: AnyGame](
    table: Table[G], action: Slug, words: str, *, arrival: str | None = None
) -> G:
    """The page's own action that opens no turn: the worldsmith writes, the narrator may tell."""
    if arrival is not None:
        table.spawner.answers.setdefault("narrator", []).append(narrated(arrival))
    await table.service.act(action, words)
    return table.state


def narrowed[M: BaseModel](value: BaseModel, model: type[M]) -> M:
    assert isinstance(value, model), f"{type(value).__name__} is not a {model.__name__}"
    return value
