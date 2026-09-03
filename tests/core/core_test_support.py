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
from aidm.core.entities import EngineId, EntityId, Refusal, Slug
from aidm.core.facts import Fact
from aidm.core.io import read_character, read_scenario, read_scenarios
from aidm.core.model import AnyGame, ScenarioKind
from aidm.core.play import Answer, Speaker
from aidm.engines.base import PLAYER_ID
from aidm.engines.hub import Campaign
from aidm.engines.loner3e.world import (
    Loner3eCharacter,
    Loner3eGame,
    Loner3eScenario,
    Loner3eSheet,
)
from aidm.engines.registry import begin_game, build_engines
from aidm.engines.seam import AnyEngine

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
BREATHLESS = EngineId("breathless")
TWENTYFOURXX = EngineId("twentyfourxx")
ENGINES_BUILT = build_engines()
ENGINE_IDS = tuple(ENGINES_BUILT)
SCENARIO_MODELS = {engine_id: engine.scenario for engine_id, engine in ENGINES_BUILT.items()}
KAEL = Speaker(name="Kael", id=PLAYER_ID)


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: Loner3eGame, entity: Loner3eSheet) -> Loner3eGame:
    """Added to the cast and to the scene; `known` alone decides present or hidden."""
    draft = state.draft()
    draft.payload.cast[entity.id] = entity
    draft.payload.run.here.append(entity.id)
    return draft.commit()


def loner_sheet(state: Loner3eGame, entity_id: EntityId) -> Loner3eSheet:
    return state.payload.require(entity_id)


def scenario() -> Loner3eScenario:
    loaded = read_scenario(SCENARIOS, "whispering-vault", SCENARIO_MODELS)
    if not isinstance(loaded, Loner3eScenario):
        raise AssertionError("the Loner scenario parsed as another engine")
    return loaded


def character() -> Loner3eCharacter:
    engine = ENGINES_BUILT[LONER3E]
    loaded = read_character(CHARACTERS, "kael", engine.id, engine.character)
    if not isinstance(loaded, Loner3eCharacter):
        raise AssertionError("the Loner character parsed as another engine")
    return loaded


def scenario_for(engine_id: EngineId, kind: ScenarioKind = "one-shot") -> Slug:
    """Read off the shipped content rather than tabulated, so a second one fails here loudly."""
    matches = [
        slug
        for slug, scenario in read_scenarios(SCENARIOS, SCENARIO_MODELS)
        if scenario.engine == engine_id and scenario.meta.kind == kind
    ]
    if len(matches) != 1:
        raise ValueError(f"{engine_id!r} ships {len(matches)} {kind} scenarios, not one: {matches}")
    return matches[0]


def game(engine_id: EngineId, kind: ScenarioKind = "one-shot") -> tuple[AnyEngine, AnyGame]:
    """The scenario authored for this engine and the shipped character, composed together."""
    engine = ENGINES_BUILT[engine_id]
    scenario_id = scenario_for(engine_id, kind)
    selected_scenario = read_scenario(SCENARIOS, scenario_id, SCENARIO_MODELS)
    selected_character = read_character(CHARACTERS, "kael", engine.id, engine.character)
    begun = begin_game(engine, scenario_id, selected_scenario, selected_character)
    return engine, begun


def shipped(engine_id: EngineId) -> tuple[ScenarioKind, ...]:
    """Which kinds this engine has a shipped scenario for, in the order they are played."""
    kinds = {
        scenario.meta.kind
        for _, scenario in read_scenarios(SCENARIOS, SCENARIO_MODELS)
        if scenario.engine == engine_id
    }
    return tuple(kind for kind in ("one-shot", "campaign") if kind in kinds)


SHIPPED: tuple[tuple[EngineId, ScenarioKind], ...] = tuple(
    (engine_id, kind) for engine_id in ENGINE_IDS for kind in shipped(engine_id)
)


def initialized() -> tuple[AnyEngine, Loner3eGame]:
    engine, state = game(LONER3E)
    if not isinstance(state, Loner3eGame):
        raise AssertionError("the Loner engine began another game type")
    return engine, state


def the_campaign(campaign: Campaign | None) -> Campaign:
    """The campaign a test built the world with, narrowed once."""
    assert campaign is not None
    return campaign


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
        if not isinstance(state, self.state_type):
            raise AssertionError(f"the service holds an unexpected {self.state_type.__name__}")
        return state

    def saved(self) -> G:
        raw = self.service.store.load(self.service.slug)
        assert raw is not None
        restored = self.service.engine.restore(raw)
        if not isinstance(restored, self.state_type):
            raise AssertionError(f"the save restored an unexpected {self.state_type.__name__}")
        return restored


def open_game(
    saves: Path,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
    engine: AnyEngine | None = None,
) -> Table[Loner3eGame]:
    return _open_game(
        saves,
        rng=rng,
        settings=settings,
        engine=engine,
        engine_id=LONER3E,
        state_type=Loner3eGame,
    )


def open_game_for(
    saves: Path,
    engine_id: EngineId,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
) -> Table[AnyGame]:
    """Open a golden-test table for whichever concrete engine is under test."""
    engine = ENGINES_BUILT[engine_id]
    return _open_game(
        saves,
        rng=rng,
        settings=settings,
        engine=engine,
        engine_id=engine_id,
        state_type=engine.game,
    )


def _open_game[G: AnyGame](
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
    service = runtime.session(LaunchTarget(scenario_id=scenario_id, character_id="kael"))
    if rng is not None:
        service.rng = rng
    return Table(runtime=runtime, service=service, spawner=spawner, state_type=state_type)


async def play_turn[G: AnyGame](
    table: Table[G],
    action: str | Answer,
    *calls: Call,
    narration: str = "You wait.",
    arrival: str | None = None,
    moving_on: bool = False,
) -> G:
    """One turn, with the game master's tool calls scripted and the narrator's answer canned."""
    table.spawner.turns.append(table.plays(calls))
    canned = table.spawner.answers.setdefault("narrator", [])
    canned.append(narrated(narration))
    # The crossing is its own narrator spawn, so a turn that installs a scene answers twice.
    if arrival is not None:
        canned.append(narrated(arrival))
    answer = Answer(text=action) if isinstance(action, str) else action
    await table.service.play(answer, moving_on=moving_on)
    return table.state
