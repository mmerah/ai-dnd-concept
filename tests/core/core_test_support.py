import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from pydantic import BaseModel, JsonValue
from pydantic_settings import SettingsConfigDict

from aidm.app import mcp
from aidm.app.launch import LaunchTarget
from aidm.app.runtime import GameService, Runtime
from aidm.app.spawn import ScriptedSpawner
from aidm.config import Settings
from aidm.content.io import load_character, load_scenario, read_scenarios
from aidm.engines.core import Engine
from aidm.engines.loner3e.engine import complete_chapter as loner_chapter
from aidm.engines.loner3e.state import ActorSheet, LonerSheet
from aidm.engines.registry import begin_game, build_engines
from aidm.kits.scenes.state import Entity
from aidm.state.entities import PLAYER_ID, EngineId, EntityId, Slug
from aidm.state.facts import Fact
from aidm.state.model import Character, Game, Scenario
from aidm.state.play import Answer, Speaker
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
ENGINES_BUILT = build_engines(REPOSITORY_ROOT / "packs")
ENGINE_IDS = tuple(ENGINES_BUILT)
KAEL = Speaker(name="Kael", id=PLAYER_ID)


def updated[T: BaseModel](model: T, **changes: object) -> T:
    """A validating copy. Production commits once per turn; a test wants the check right here."""
    return type(model).model_validate(model.model_dump(round_trip=True) | changes)


def with_entity(state: Game, entity: Entity[LonerSheet]) -> Game:
    """Added to the cast and to the scene, because a scene entity is where a scene entity lives."""
    draft = state.draft()
    draft.world.cast[entity.id] = entity
    current = draft.world.current
    draft.world.current = current.model_copy(update={"present": (*current.present, entity.id)})
    return draft.committed()


def loner_at_boundary(state: Game) -> Game:
    draft = state.draft()
    _ = loner_chapter(draft)
    return draft.committed()


def loner_sheet(state: Game, entity_id: EntityId) -> ActorSheet:
    sheet = state.world.require(entity_id).sheet
    if not isinstance(sheet, ActorSheet):
        raise AssertionError(f"{entity_id!r} has no actor sheet")
    return sheet


def scenario() -> Scenario:
    return load_scenario(SCENARIOS, "whispering-vault", ENGINES_BUILT[LONER3E])


def character() -> Character:
    return load_character(CHARACTERS, "kael", ENGINES_BUILT[LONER3E])


def scenario_for(engine_id: EngineId) -> Slug:
    """Read off the shipped content rather than tabulated, so a second one fails here loudly."""
    shipped = [
        slug
        for slug, scenario in read_scenarios(SCENARIOS, ENGINES_BUILT)
        if scenario.engine == engine_id
    ]
    if len(shipped) != 1:
        raise ValueError(f"{engine_id!r} ships {len(shipped)} scenarios, not one: {shipped}")
    return shipped[0]


def game(engine_id: EngineId) -> tuple[Engine, Game]:
    """The scenario authored for this engine and the shipped character, composed together."""
    engine = ENGINES_BUILT[engine_id]
    scenario_id = scenario_for(engine_id)
    selected_scenario = load_scenario(SCENARIOS, scenario_id, engine)
    selected_character = load_character(CHARACTERS, "kael", engine)
    return engine, begin_game(engine, scenario_id, selected_scenario, selected_character)


def initialized() -> tuple[Engine, Game]:
    return game(LONER3E)


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
class Table:
    """A live game and the tool surface a scripted game master plays it through."""

    runtime: Runtime
    service: GameService
    spawner: ScriptedSpawner
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

    def saved(self) -> Game:
        raw = self.service.store.load(self.service.slug)
        assert raw is not None
        return self.service.engine.restored(raw)


def opened(
    saves: Path,
    *,
    rng: Random | None = None,
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> Table:
    settings = settings or offline_settings(saves)
    spawner = ScriptedSpawner()
    runtime = Runtime(settings, spawner)
    if engine is not None:
        runtime.engines[LONER3E] = engine
    scenario_id = scenario_for(LONER3E)
    service = runtime.session(
        LaunchTarget(slug=f"{scenario_id}--kael", scenario_id=scenario_id, character_id="kael")
    )
    if rng is not None:
        service.rng = rng
    return Table(runtime=runtime, service=service, spawner=spawner)


async def played(
    table: Table,
    action: str | Answer,
    *calls: Call,
    narration: str = "You wait.",
    arrival: str | None = None,
    start: bool = True,
    moving_on: bool = False,
    on_step: Callable[[TurnStep], None] | None = None,
    on_fact: Callable[[Fact], None] | None = None,
) -> Game:
    """One turn, with the game master's tool calls scripted and the narrator's answer canned."""
    table.spawner.turns.append(table.plays(calls, start=start))
    canned = table.spawner.answers.setdefault("narrator", [])
    canned.append(narrated(narration))
    # The crossing is its own narrator spawn, so a turn that installs a scene answers twice.
    if arrival is not None:
        canned.append(narrated(arrival))
    await table.service.play(action, on_step=on_step, on_fact=on_fact, moving_on=moving_on)
    return table.service.state
