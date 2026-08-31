import logging
from asyncio import Lock, Task, create_task
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from random import Random

from aidm.config import Settings, load_settings
from aidm.core.entities import EngineId, EntityId, Slug, require_unique, slug
from aidm.core.facts import Fact, told_traces, traced
from aidm.core.io import FileStore, load_character, read_scenario, write_scenario
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
from aidm.core.tools import MasterTool
from aidm.core.views import NarratorView, PlayerView
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engines
from aidm.kits.scenes.worldsmith import opening_canon, scene_refusal
from aidm.turn.context import (
    CROSSING,
    render_master,
    render_narrator,
    render_opening,
    told_passages,
)
from aidm.turn.run import (
    TURN_TOOLS,
    Turn,
    TurnStep,
    TurnTool,
    close_segment,
    narration_refusal,
)

from .launch import LaunchTarget
from .media import Illustrator, open_illustrator
from .scene_write import install_scene, write_next
from .spawn import CliSpawner, Spawner, answered

LOGGER = logging.getLogger(__name__)

# What the crossing is filed under in the chronicle: the player took no action in it.
CROSSED = "(the story moves on)"


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
        if moving_on and not self.state.world.run.settled:
            raise ValueError("this scene has no way on yet; play it out first")

        def announce(step: TurnStep) -> None:
            self.step = step
            if on_step is not None:
                on_step(step)

        turn = Turn.begin(
            self.engine, self.state, action, self.rng, self.settings.turn.recent_exchanges, on_fact
        )
        self.busy, self.turn, self.write_failure = True, turn, ""
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
            self._illustrate(state.world.run.exchanges[-1].narration)
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
                lambda written: narration_refusal(view, written),
                partial(self.spawner.run, "narrator"),
            )
        except (OSError, ValueError) as failed:
            if fatal:
                raise
            # The scene cost minutes to write; an unwritable crossing must not throw it away.
            LOGGER.warning("the crossing went unnarrated: %s", failed)
            return ()
        return narration.lines

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
                facts = install_scene(self.engine, draft, written)
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
        self._illustrate(self.state.world.run.exchanges[-1].narration)

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
        try:
            return await write_next(
                snapshot, intent, self.engine, partial(self.spawner.run, "worldsmith")
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

    def default_engine(self) -> EngineId:
        """Dict order picks it; a create page has to start somewhere."""
        return next(iter(self.engines))

    def published_tools(self) -> tuple[TurnTool | MasterTool, ...]:
        """A CLI lists tools only inside its own turn, so with none open any engine will do."""
        playing = self.playing()
        engine = playing.engine if playing is not None else self.engines[self.default_engine()]
        published = (*TURN_TOOLS, *engine.tools)
        require_unique("published tool names", (one.name for one in published))
        return published

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
        engine_id: EngineId,
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
        engine = self.engines[engine_id]
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
            """The rules judge the opening, so an unplayable actor costs a re-prompt, not a file."""
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
        scenario = read_scenario(settings.scenarios_dir, target.scenario_id)
        engine = self.engines[scenario.engine]
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
            media=open_illustrator(settings, target, scenario, character, store),
        )
