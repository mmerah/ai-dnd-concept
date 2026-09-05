import logging
from asyncio import Lock, Task, create_task
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from random import Random

from aidm.app.launch import LaunchTarget
from aidm.app.media import ICON_DIR, Illustrator, open_illustrator
from aidm.app.spawn import CliSpawner, Spawner, ask
from aidm.app.speech import Reader, open_reader
from aidm.config import Role, Settings, read_settings
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import Fact, cards, traced
from aidm.core.io import FileStore, Library, decode
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import Answer, Exchange, Line, Narration
from aidm.core.source import given_text
from aidm.core.tools import MasterTool
from aidm.core.views import PlayerView
from aidm.engines.registry import build_engines
from aidm.engines.seam import AnyEngine
from aidm.turn.context import render_narrator
from aidm.turn.run import Turn

LOGGER = logging.getLogger(__name__)

# What a turn nobody played is filed under in the chronicle: the crossing, and the opening.
CROSSED = "(the story moves on)"
BEGUN = "(the story begins)"
UNWRITTEN = Fact(
    kind="way_unwritten",
    told=True,
    trace="the way on could not be written",
    card="The way on could not be written. You are still where you were.",
)
PAUSED = (
    'play pauses here on the player\'s decision: "{prompt}" End on the pause; settle nothing they '
    "have not yet answered."
)
OPENING = (
    "The story begins here; the player has read nothing yet. Tell them, in the fiction and in "
    "this order: who they are (WHO IS HERE names them first) and where they stand; what is in "
    "front of them, the situation as they see it now; what they are here to do, from WHAT THIS "
    "SCENE IS ABOUT, said as the thing pulling at them; and two or three things they could "
    "plainly do first, offered by the place and the people, in prose, never as a list. Six to "
    "eight sentences. They have not acted, so settle nothing."
)


@dataclass(slots=True)
class GameService:
    target: LaunchTarget
    scenario: AnyScenario
    character: AnyCharacter
    engine: AnyEngine
    spawner: Spawner
    store: FileStore
    media: Illustrator | None = None
    reader: Reader | None = None
    rng: Random = field(default_factory=Random)
    # The role at work; the play page polls it and binds its widgets to it.
    phase: Role | None = None
    # What the player typed for a write that opens no turn; the page shows it as their bubble.
    intent: str = ""
    # The turn in flight; the tool surface reaches the live game through it.
    turn: Turn | None = None
    _background: set[Task[None]] = field(default_factory=set, repr=False)
    state: AnyGame = field(init=False)

    def __post_init__(self) -> None:
        saved = self.store.load(self.slug)
        if saved is None:
            self.state = self._begin()
            return
        self.state = self._resumable(self.engine.restore(decode(saved)))

    @property
    def slug(self) -> str:
        return self.target.slug

    @property
    def busy(self) -> bool:
        return self.phase is not None

    def unopened(self) -> bool:
        return not self.busy and not self.engine.history(self.state)

    async def open(self) -> None:
        """A failed narrator leaves the premise to do its work; a reload mid-opening is a no-op."""
        if not self.unopened():
            return
        self.phase = "narrator"
        try:
            draft = self.state.draft()
            lines = await self._narrate(draft, (), OPENING, fatal=False)
            if lines:
                self.commit(self.engine.close(draft, BEGUN, lines, ()))
            self._present()
        finally:
            self.phase = None

    async def play(self, answer: Answer, *, moving_on: bool = False) -> None:
        """`moving_on` is the player taking the way on, so `answer` is what they mean to pursue.

        A crossing of `None` means the world grows without a turn: `extend` runs instead.
        """
        brief = self.engine.crossing(self.state, answer.text) if moving_on else None
        if moving_on and brief is None:
            await self.extend(answer)
            return
        if moving_on and not self.engine.ready(self.state):
            raise Refusal("the world offers no transition from here")
        mastered = not (moving_on and self.engine.page_word(self.state, answer.text))
        turn = Turn.begin(self.engine, self.state, answer, self.rng, mastered=mastered)
        self.turn, self.phase = turn, "master"
        try:
            # An answer that re-suspended leaves every tool refused: nothing for a master to do.
            if mastered and turn.draft.pending is None:
                await self._act(turn)
            lines: tuple[Line, ...] = ()
            if turn.draft.pending is None or any(fact.told for fact in turn.facts):
                self.phase = "narrator"
                lines = await self._narrate(turn.draft, tuple(turn.facts), turn.prompt, fatal=True)
            state = turn.finish(lines)
            # Cleared before arrival: the tool surface must not reach a turn nobody plays.
            self.turn = None
            self.commit(state)
            self._present()
            # The player named where they go; the worldsmith writes it once the turn is safe.
            if brief is not None and self.engine.over(state) is None:
                await self._grow(turn.prompt, brief)
                self._present()
        finally:
            self.turn, self.phase = None, None

    def _present(self) -> None:
        newest = self._newest()
        self.illustrate("" if newest is None else newest.narration)
        self.speak()

    async def extend(self, answer: Answer) -> None:
        """Author and install a region without a player turn; a told card is still filed."""
        if not self.engine.ready(self.state):
            raise Refusal("the world has no frontier to extend")
        if self.busy:
            raise Refusal("a turn is already in flight")
        if answer.option_id is not None:
            raise Refusal("a transition needs written intent")
        self.intent = answer.text
        try:
            await self._grow(answer.text, None)
            self._present()
        finally:
            self.intent, self.phase = "", None

    async def _act(self, turn: Turn) -> None:
        """A crashed game master still played the turn, if it applied anything legal first."""

        def nothing_landed() -> bool:
            return not turn.facts and turn.draft.pending is None

        prompt = turn.picture()
        for last in (False, True):
            try:
                await self.spawner.run("master", prompt, None)
                return
            except (OSError, Refusal) as failed:
                if not nothing_landed():
                    LOGGER.warning(
                        "the game master failed after applying %d facts: %s",
                        len(turn.facts),
                        failed,
                    )
                    return
                if last:
                    raise
                LOGGER.warning("the game master landed nothing, spawning it again: %s", failed)

    async def _narrate(
        self, draft: AnyGame, facts: tuple[Fact, ...], prompt: str, *, fatal: bool
    ) -> tuple[Line, ...]:
        view = self.engine.narrator_view(draft)
        evidence = traced(facts, told_only=True)
        if (pending := draft.pending) is not None:
            evidence += f"\n- {PAUSED.format(prompt=pending.prompt)}"
        try:
            narration = await ask(
                self.spawner,
                "narrator",
                render_narrator(
                    view, evidence=evidence, prompt=prompt, scenes=self.engine.scenes(draft)
                ),
                Narration,
                view.narration_refusal,
            )
        except (OSError, Refusal) as failed:
            if fatal:
                raise
            # The scene cost minutes to write; an unwritable arrival must not throw it away.
            LOGGER.warning("the arrival went unnarrated: %s", failed)
            return ()
        return narration.lines

    async def _grow(self, intent: str, brief: str | None) -> None:
        self.phase = "worldsmith"
        draft = self.state.draft()
        try:
            facts = await self.engine.advance(draft, intent, _worldsmith(self.spawner))
        except (OSError, Refusal) as failed:
            # Dropping the write costs a scene; raising costs the turn that was already played.
            LOGGER.warning("the world did not grow: %s", failed)
            # A fresh draft: the failed one may hold the half-installed scene.
            draft = self.state.draft()
            # The turn already filed the player's words when a crossing was asked for.
            prompt = intent if brief is None else CROSSED
            self.commit(self.engine.close(draft, prompt, (), (UNWRITTEN,)))
            return
        if brief is None and not cards(facts):
            self.commit(self.engine.commit(draft))
            return
        self.phase = "narrator"
        lines = await self._narrate(draft, facts, brief or intent, fatal=False)
        self.commit(self.engine.close(draft, intent if brief is None else CROSSED, lines, facts))

    def player_view(self) -> PlayerView:
        return self.engine.player_view(self.state)

    def scene_art(self) -> Path | None:
        if self.media is None:
            return None
        return self.media.scene_art(self.engine.narrator_view(self.state))

    def icon(self, entity_id: EntityId) -> Path | None:
        return None if self.media is None else self.media.icon(entity_id)

    def newest_clip(self) -> Path | None:
        newest = self._newest()
        return None if self.reader is None or newest is None else self.reader.clip(newest)

    def illustrate(self, narration: str = "") -> None:
        if self.media is None:
            return
        view = self.engine.narrator_view(self.state)
        task = create_task(self.media.illustrate(view, self.player_view().player, narration))
        self._retain(task)

    def speak(self) -> None:
        """The newest exchange is read after it commits; old ones are never generated."""
        newest = self._newest()
        if self.reader is None or newest is None:
            return
        self._retain(create_task(self.reader.read(newest)))

    def _newest(self) -> Exchange | None:
        history = self.engine.history(self.state)
        return history[-1] if history else None

    def _retain(self, task: Task[None]) -> None:
        """Retain background tasks because asyncio may collect unreferenced tasks early."""
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    def restart(self) -> None:
        opening = self._begin()
        self.store.discard(self.slug)
        self.state = opening

    def commit(self, state: AnyGame) -> None:
        self.store.save(self.slug, state)
        self.state = state

    def _begin(self) -> AnyGame:
        return self.engine.begin(self.target.scenario_id, self.scenario, self.character)

    def _resumable(self, state: AnyGame) -> AnyGame:
        if (state.scenario_id, state.character_id) != (self.target.scenario_id, self.character.id):
            raise Refusal(
                f"save is {state.scenario_id!r}/{state.character_id!r}, "
                f"selected is {self.target.scenario_id!r}/{self.character.id!r}"
            )
        if state.scenario != self.scenario.meta:
            raise Refusal(
                f"save scenario is {state.scenario.title!r}, "
                f"selected scenario is {self.scenario.meta.title!r}"
            )
        return state


@dataclass(slots=True)
class Runtime:
    """The composition root: settings, the built engine, the spawner, and the games open."""

    settings: Settings
    spawner: Spawner
    _sessions: dict[str, GameService] = field(default_factory=dict, repr=False)
    lock: Lock = field(default_factory=Lock, repr=False)
    engines: dict[EngineId, AnyEngine] = field(init=False)
    library: Library = field(init=False)
    store: FileStore = field(init=False)

    def __post_init__(self) -> None:
        self.engines = build_engines()
        self._mount()

    def _mount(self) -> None:
        self.library = Library(self.settings.scenarios_dir, self.settings.characters_dir)
        self.store = FileStore(self.settings.saves_dir)

    def default_engine(self) -> EngineId:
        """Dict order picks it; a create page has to start somewhere."""
        return next(iter(self.engines))

    def published_tools(self) -> tuple[MasterTool[AnyGame], ...]:
        """A CLI lists tools only inside its own turn; between turns there is nothing to call."""
        playing = self.playing()
        return () if playing is None else tuple(playing.engine.tools.values())

    def playing(self) -> GameService | None:
        """A second turn in flight has no owner: the tool surface is shared."""
        in_flight = [session for session in self._sessions.values() if session.turn is not None]
        if len(in_flight) > 1:
            raise ValueError(f"turns are in flight in {[session.slug for session in in_flight]}")
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
        self.settings = read_settings()
        self.spawner = CliSpawner(self.settings)
        self._mount()
        self._sessions.clear()

    async def new_scenario(
        self,
        engine_id: EngineId,
        meta: ScenarioMeta,
        document: Path | None,
        packs: Sequence[Slug],
        character_id: Slug,
    ) -> Slug:
        """One worldsmith call authors the engine's complete opening world."""
        engine = self.engines[engine_id]
        character = self.library.read_character(character_id, engine.id, engine.character)
        source = given_text(meta.premise, document, self.settings.source_max_chars)
        name = slug(meta.title, self.library.scenario_ids())

        def playable(built: AnyScenario) -> str | None:
            try:
                engine.begin(name, built, character)
            except Refusal as unplayable:
                return str(unplayable)
            return None

        scenario = await engine.author(meta, source, packs, _worldsmith(self.spawner), playable)
        self.library.write_scenario(name, scenario, document)
        LOGGER.info("scenario written: slug=%s title=%r", name, meta.title)
        return name

    def session(self, target: LaunchTarget) -> GameService:
        """Memoised: a page render must not rebuild the game and drop the turn in flight."""
        if target.slug not in self._sessions:
            self._sessions[target.slug] = self._open(target)
        return self._sessions[target.slug]

    def _open(self, target: LaunchTarget) -> GameService:
        settings = self.settings
        scenario = self.library.read_scenario(
            target.scenario_id,
            {engine_id: engine.scenario for engine_id, engine in self.engines.items()},
        )
        engine = self.engines[scenario.engine]
        character = self.library.read_character(target.character_id, engine.id, engine.character)
        return GameService(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            spawner=self.spawner,
            store=self.store,
            media=open_illustrator(
                settings,
                self.store,
                target.slug,
                style=scenario.meta.art_style or engine.art_style,
                icon_dirs=(
                    self.library.scenario_folder(target.scenario_id) / ICON_DIR,
                    self.library.character_folder(target.character_id) / ICON_DIR,
                ),
            ),
            reader=open_reader(
                settings,
                self.store,
                target.slug,
                voice=scenario.meta.voice or settings.speech.voice,
            ),
        )


def _worldsmith(spawner: Spawner) -> WorldsmithAnswer:
    """What the platform hands an engine: one spawned role, one shared retry."""
    return partial(ask, spawner, "worldsmith")
