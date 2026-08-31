import logging
from asyncio import Lock, Task, create_task
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.config import Settings, load_settings
from aidm.core.entities import EngineId, EntityId, Slug, slug
from aidm.core.facts import Fact, told_traces, traced
from aidm.core.io import (
    FileStore,
    load_character,
    scenario_envelope,
    scenario_of,
    write_scenario,
)
from aidm.core.model import (
    Character,
    Game,
    Scenario,
    ScenarioMeta,
    ScenarioPayload,
    SceneWrite,
)
from aidm.core.play import Answer, Line, Narration
from aidm.core.source import given_text
from aidm.core.tools import NoArgs
from aidm.core.views import NarratorView, PlayerView
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engines
from aidm.kits.scenes.worldsmith import apply_scene, opening_canon, scene_refusal
from aidm.turn.context import (
    CROSSING,
    render_master,
    render_narrator,
    render_opening,
    render_picture,
    render_worldsmith,
    told_passages,
)
from aidm.turn.run import Turn, TurnStep, close_segment, speakers_refusal

from .launch import LaunchTarget
from .media import ICON_DIR, Illustrator
from .spawn import CliSpawner, Spawner, answered

LOGGER = logging.getLogger(__name__)

NO_TURN = "no turn is open. The player starts one from the page; wait to be spawned again."
OFFERED = (
    "the player is choosing where to go; their answer opens the next scene. "
    "This turn is not over — finish what their action caused, then exit."
)
# What the crossing is filed under in the chronicle: the player took no action in it.
CROSSED = "(the story moves on)"
START_FIRST = "call `start_turn` first: it opens the turn and hands back the picture."
ALREADY_OPEN = "the turn is already open. `scene` gives the picture back."
DECIDING = "the rules are waiting on the player; the scene after this one waits with them."


@dataclass
class GameService:
    target: LaunchTarget
    scenario: Scenario
    character: Character
    engine: Engine
    spawner: Spawner
    store: FileStore
    settings: Settings
    media: Illustrator | None = None
    rng: Random = field(default_factory=Random)
    # A plain attribute, not a property: the play page binds its widgets to it.
    busy: bool = False
    step: TurnStep | None = None
    # The turn in flight; the tool surface reaches the live game through it.
    turn: Turn | None = None
    # The game master has called `start_turn`; nothing may change the world before it does.
    turn_started: bool = False
    # The game master's whole output, raw, for the dev tab; one spawn, so one string.
    master_log: str = ""
    # Why the last scene write failed or would not fit; empty when none has.
    write_failure: str = ""
    _illustrations: set[Task[None]] = field(default_factory=set, repr=False)
    _writing: Task[SceneWrite | None] | None = field(default=None, repr=False)
    state: Game = field(init=False)

    def __post_init__(self) -> None:
        saved = self.store.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(self.engine.restored(saved))

    @property
    def slug(self) -> str:
        return self.target.slug

    async def play(
        self,
        action: str | Answer,
        on_step: Callable[[TurnStep], None] | None = None,
        on_fact: Callable[[Fact], None] | None = None,
        *,
        moving_on: bool = False,
    ) -> None:
        """`moving_on` is the player taking the way on, so `action` is what they mean to pursue."""
        if moving_on and not self.state.world.settled:
            raise ValueError("this scene has no way on yet; play it out first")

        def announce(step: TurnStep) -> None:
            self.step = step
            if on_step is not None:
                on_step(step)

        turn = Turn.begin(self.engine, self.state, action, self.rng, on_fact)
        self.busy, self.turn, self.turn_started, self.write_failure = True, turn, False, ""
        try:
            # The player named where they go; the worldsmith writes while the turn still plays.
            if moving_on:
                self._write_scene(turn.prompt)
            announce("master")
            await self._act(turn)
            lines: tuple[Line, ...] = ()
            if turn.draft.pending is None or told_traces(turn.facts):
                announce("narrator")
                lines = await self._narrate(turn.draft, tuple(turn.facts), turn.prompt, fatal=True)
            state = turn.finish(lines)
            # Cleared before the crossing: the tool surface must not reach a turn nobody plays.
            self.turn, self.step = None, None
            self.commit(state)
            self._illustrate(state.history[-1].narration)
            await self._cross_over(announce, turn.prompt)
        except BaseException:
            self._abandon_write()
            raise
        finally:
            self.turn, self.step, self.busy = None, None, False

    async def _act(self, turn: Turn) -> None:
        """A crashed game master still played the turn, if it applied anything legal first."""
        self.master_log = ""
        try:
            self.master_log = await self.spawner.run(
                "master", render_master(self.engine.instructions, turn.prompt)
            )
        except (OSError, ValueError) as failed:
            if not turn.facts and turn.draft.pending is None:
                raise
            LOGGER.warning(
                "the game master failed after applying %d facts: %s", len(turn.facts), failed
            )

    async def _narrate(
        self, draft: Game, facts: tuple[Fact, ...], prompt: str, *, fatal: bool
    ) -> tuple[Line, ...]:
        view = self.engine.narrator_view(draft)
        try:
            narration = await answered(
                "narrator",
                render_narrator(
                    view,
                    evidence=traced(facts, told_only=True),
                    prompt=prompt,
                    passages=told_passages(draft, self.settings.turn.recent_exchanges),
                ),
                Narration,
                lambda written: _narration_refusal(view, written),
                partial(self.spawner.run, "narrator"),
            )
        except (OSError, ValueError) as failed:
            if fatal:
                raise
            # The scene cost minutes to write; an unwritable crossing must not throw it away.
            LOGGER.warning("the crossing went unnarrated: %s", failed)
            return ()
        return narration.lines

    def call_tool(self, name: str, raw: dict[str, JsonValue]) -> str:
        turn = self._require_turn()
        if (refused := self._tool_refusal(turn, name)) is not None:
            raise ValueError(refused)
        served = _DISPATCH.get(name)
        if served is None:
            return self._engine_call(turn, name, raw)
        # A server tool takes no arguments, so junk ones need a guard of their own.
        _ = NoArgs.model_validate(raw)
        return served.run(self)

    def start_turn(self) -> str:
        self.turn_started = True
        return self.picture()

    def picture(self) -> str:
        turn = self._require_turn()
        return render_picture(
            self.engine.master_sections(turn.draft),
            turn.draft,
            turn.prompt,
            resumed=turn.resumed,
            notes=(*turn.notes, *turn.draft.notes),
            recent=self.settings.turn.recent_exchanges,
        )

    def offer_the_way_on(self) -> str:
        self._require_turn().settle_scene()
        return OFFERED

    def _tool_refusal(self, turn: Turn, name: str) -> str | None:
        if name == "scene":
            return None
        if name == "start_turn":
            return ALREADY_OPEN if self.turn_started else None
        if not self.turn_started:
            return START_FIRST
        if (ended := self.engine.over(turn.draft)) is not None:
            return f"{ended} The game is over; the player restarts from the page."
        # `next_scene` changes the world without reaching the engine, so its pending row is here.
        if name == "next_scene" and turn.draft.pending is not None:
            return DECIDING
        return None

    def _engine_call(self, turn: Turn, name: str, raw: Mapping[str, JsonValue]) -> str:
        """The one gate: a decision on the table blocks everything but developing its answer."""
        found = next((one for one in self.engine.tools if one.name == name), None)
        if found is None:
            raise ValueError(f"{name!r} is not a tool of the {self.engine.id!r} engine.")
        pending = turn.draft.pending
        if pending is not None and not (found.during_suspension and turn.suspended_at_start):
            # A plain answer, not a refusal: a retry prompt would tell the model to try again.
            return (
                f"the rules are waiting on the player: {pending.prompt}\n"
                "Stop here and exit; the player's answer opens the next turn."
            )
        return turn.apply(lambda draft, rng: found.call(draft, raw, rng))

    def _require_turn(self) -> Turn:
        turn = self.turn
        if turn is None:
            raise ValueError(NO_TURN)
        return turn

    async def _cross_over(self, announce: Callable[[TurnStep], None], pursuit: str) -> None:
        if self._writing is None:
            return
        if self.engine.over(self.state) is not None:
            self._abandon_write()
            return
        writing, self._writing = self._writing, None
        try:
            announce("worldsmith")
            written = await writing
            if written is None:
                return
            draft = self.state.draft()
            try:
                facts = _installed(self.engine, draft, written)
            except ValueError as outgrown:
                # Dropping the scene costs a scene; raising costs the turn that was already played.
                self.write_failure = str(outgrown)
                LOGGER.warning("the written scene no longer fits the world: %s", outgrown)
                return
            announce("narrator")
            lines = await self._narrate(draft, facts, CROSSING.format(pursuit=pursuit), fatal=False)
            view = self.engine.narrator_view(draft)
            self.commit(close_segment(view, draft, CROSSED, lines, facts))
        finally:
            self.step = None
        self._illustrate(self.state.history[-1].narration)

    def _abandon_write(self) -> None:
        """Cancelled, not just dropped: a write left running would install a scene a turn late."""
        if self._writing is not None:
            _ = self._writing.cancel()
        self._writing = None

    def _write_scene(self, intent: str) -> None:
        self._abandon_write()
        # A deep copy, never the live state: the turn keeps playing while this runs.
        self._writing = create_task(self._write(self.state.draft(), intent))

    async def _write(self, snapshot: Game, intent: str) -> SceneWrite | None:
        prompt = render_worldsmith(
            snapshot.world,
            snapshot.history,
            intent,
            self.engine.guidance(snapshot.packs),
            self.engine.sheet_rows(snapshot),
        )
        try:
            return await answered(
                "worldsmith",
                prompt,
                SceneWrite,
                lambda written: scene_refusal(written, snapshot.world),
                partial(self.spawner.run, "worldsmith"),
            )
        except (OSError, ValueError) as failed:
            self.write_failure = str(failed)
            LOGGER.warning("the worldsmith wrote no scene: %s", failed)
            return None

    def player_view(self) -> PlayerView:
        return self.engine.player_view(self.state)

    def scene(self) -> NarratorView:
        return self.engine.narrator_view(self.state)

    def scene_art(self) -> Path | None:
        return None if self.media is None else self.media.scene_art(self.scene())

    def scene_pending(self) -> bool:
        return self.media is not None and self.media.scene_pending(self.scene())

    def illustrate_scene(self) -> None:
        """Draw where the player stands with no turn behind it, so an opening scene has art."""
        self._illustrate("")

    def icon(self, entity_id: EntityId) -> Path | None:
        return None if self.media is None else self.media.icon(entity_id)

    def _illustrate(self, narration: str) -> None:
        """Retain background tasks because asyncio may collect unreferenced tasks early."""
        if self.media is None:
            return
        task = create_task(
            self.media.illustrate(self.scene(), self.player_view().player, narration)
        )
        self._illustrations.add(task)
        task.add_done_callback(self._illustrations.discard)

    def restart(self) -> None:
        opening = self._begun()
        self.store.discard(self.slug)
        self.state = opening
        self.illustrate_scene()

    def commit(self, state: Game) -> None:
        self.store.save(self.slug, state)
        self.state = state

    def _begun(self) -> Game:
        return begin_game(self.engine, self.target.scenario_id, self.scenario, self.character)

    def _resumable(self, state: Game) -> Game:
        if (state.scenario_id, state.character_id) != (self.target.scenario_id, self.character.id):
            raise ValueError(
                f"save is {state.scenario_id!r}/{state.character_id!r}, "
                f"selected is {self.target.scenario_id!r}/{self.character.id!r}"
            )
        if state.scenario != self.scenario.meta:
            raise ValueError(
                f"save scenario is {state.scenario.title!r}, "
                f"selected scenario is {self.scenario.meta.title!r}"
            )
        self.engine.validate(state)
        return state


@dataclass(frozen=True, slots=True)
class ServerTool:
    name: str
    description: str
    run: Callable[[GameService], str]


SERVER_TOOLS: tuple[ServerTool, ...] = (
    ServerTool(
        "start_turn",
        "Open the turn and get the whole game back: the scene, who is here, what is hidden here,"
        " the threads, the notes from the rules and the recent play. Call it first every turn.",
        GameService.start_turn,
    ),
    ServerTool(
        "scene",
        "The same picture start_turn gives, for when you were compacted mid-turn.",
        GameService.picture,
    ),
    ServerTool(
        "next_scene",
        "Say this scene's question is settled. The player is then asked what they want to pursue,"
        " and their own words are what the next scene is built from. Do not answer for them.",
        GameService.offer_the_way_on,
    ),
)

_DISPATCH = {tool.name: tool for tool in SERVER_TOOLS}


@dataclass(slots=True)
class Runtime:
    """The composition root: settings, the built engine, the spawner, and the games open."""

    settings: Settings
    spawner: Spawner
    _sessions: dict[str, GameService] = field(default_factory=dict, repr=False)
    lock: Lock = field(default_factory=Lock, repr=False)
    engines: dict[EngineId, Engine] = field(init=False)

    def __post_init__(self) -> None:
        self.engines = build_engines(self.settings.packs_dir)

    @property
    def engine(self) -> Engine:
        """One engine ships, and the tool surface publishes before a game is even open."""
        return next(iter(self.engines.values()))

    def playing(self) -> GameService | None:
        """A second turn in flight has no owner: the tool surface is shared."""
        in_flight = [one for one in self._sessions.values() if one.turn is not None]
        if len(in_flight) > 1:
            raise ValueError(f"turns are in flight in {[one.slug for one in in_flight]}")
        return in_flight[0] if in_flight else None

    def busy_refusal(self) -> str | None:
        """Evicting a session mid-turn would let the next tab open a rival writer on that save."""
        playing = [slug for slug, session in self._sessions.items() if session.busy]
        return f"A turn is in flight in {playing[0]!r}." if playing else None

    def play_refusal(self, session: GameService) -> str | None:
        """A settings reload drops every session, but a page can still hold one."""
        if self._sessions.get(session.slug) is not session:
            return "The settings changed. Reload this page before you play on."
        return self.busy_refusal()

    def reload_settings(self) -> None:
        self.settings = load_settings()
        self.engines = build_engines(self.settings.packs_dir)
        self.spawner = CliSpawner(self.settings)
        self._sessions.clear()

    async def new_scenario(
        self,
        title: str,
        premise: str,
        document: Path | None,
        packs: Sequence[Slug],
        character_id: Slug,
    ) -> Slug:
        """One worldsmith call, before any game exists: the opening scene is the scenario."""
        # `Scenario` refuses an empty pack tuple, but only after the write; refuse it before.
        if not packs:
            raise ValueError("a scenario needs at least one table set")
        engine = self.engine
        character = load_character(self.settings.characters_dir, character_id, engine.id)
        source = given_text(premise, document, self.settings.source.max_chars)
        name = slug(title, self._scenario_ids())

        def as_scenario(scene: SceneWrite) -> Scenario:
            return Scenario(
                meta=ScenarioMeta(title=title, premise=premise or scene.situation),
                engine=engine.id,
                packs=tuple(packs),
                payload=ScenarioPayload(world=opening_canon(scene, source)),
            )

        def refusal(scene: SceneWrite) -> str | None:
            """The rules judge the opening too, so an actor the engine will not play costs the
            re-prompt rather than a scenario file nothing can ever open."""
            refused = scene_refusal(scene)
            if refused is not None:
                return refused
            try:
                _ = begin_game(engine, name, as_scenario(scene), character)
            except ValueError as unplayable:
                return str(unplayable)
            return None

        scene = await answered(
            "worldsmith",
            render_opening(source, engine.guidance(packs)),
            SceneWrite,
            refusal,
            partial(self.spawner.run, "worldsmith"),
        )
        write_scenario(self.settings.scenarios_dir, name, as_scenario(scene), document)
        LOGGER.info("scenario written: slug=%s title=%r", name, title)
        return name

    def _scenario_ids(self) -> tuple[str, ...]:
        directory = self.settings.scenarios_dir
        return tuple(one.name for one in directory.iterdir()) if directory.is_dir() else ()

    def session(self, target: LaunchTarget) -> GameService:
        """Memoised: a page render must not rebuild the game and drop the turn in flight."""
        held = self._sessions.get(target.slug)
        if held is not None:
            if held.target != target:
                raise ValueError(f"open session {target.slug!r} plays {held.target}, not {target}")
            return held
        opened = self._open(target)
        self._sessions[target.slug] = opened
        return opened

    def _open(self, target: LaunchTarget) -> GameService:
        settings = self.settings
        envelope = scenario_envelope(settings.scenarios_dir, target.scenario_id)
        engine = self.engines[envelope.engine]
        scenario = scenario_of(envelope, engine.id)
        character = load_character(settings.characters_dir, target.character_id, engine.id)
        store = FileStore(settings.saves_dir)
        return GameService(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            spawner=self.spawner,
            store=store,
            settings=settings,
            media=_open_media(settings, target, scenario, character, store),
        )


def _open_media(
    settings: Settings,
    target: LaunchTarget,
    scenario: Scenario,
    character: Character,
    store: FileStore,
) -> Illustrator | None:
    """Share authored icons across games while keeping generated canon and scenes per save."""
    if not settings.media.enabled:
        return None
    scenario_icons = settings.scenarios_dir / target.scenario_id / ICON_DIR
    character_icons = settings.characters_dir / target.character_id / ICON_DIR
    return Illustrator(
        config=settings.media,
        provider=settings.providers.for_name(settings.media.provider),
        saves=store.media_dir(target.slug),
        icon_dirs=(scenario_icons, character_icons),
        style=scenario.art_style or settings.media.style,
    )


def _narration_refusal(view: NarratorView, written: Narration) -> str | None:
    if not written.text:
        return "write the narration lines: an empty answer shows the player nothing."
    return speakers_refusal(view, written.lines)


def _installed(engine: Engine, draft: Game, written: SceneWrite) -> tuple[Fact, ...]:
    """What the rules settle as the old scene ends, then the new scene itself."""
    closed = engine.scene_closed(draft)
    # A deep copy: the trial run and the real one must not share the entities the scene brings.
    apply_scene(draft.world, written.model_copy(deep=True), draft.turn)
    # Companions cross by code, so nothing else would tell the narrator they came along.
    came = [draft.world.require(one).name for one in draft.world.companions]
    trace = f"the story moves to {written.title}"
    if came:
        trace += f", and {', '.join(came)} travels there with the player"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"New scene: {written.title}")
    return (*closed, opened)
