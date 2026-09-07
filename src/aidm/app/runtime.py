import logging
from asyncio import Lock, Task, create_task
from collections.abc import Mapping, Sequence
from dataclasses import InitVar, dataclass, field
from functools import partial
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.app.builtin import BuiltinSpawner
from aidm.app.launch import LaunchTarget
from aidm.app.media import ICON_DIR, Illustrator, open_illustrator
from aidm.app.spawn import CliSpawner, RunResult, Spawner, ask
from aidm.app.speech import Reader, open_reader
from aidm.config import Role, Settings, read_settings
from aidm.core.entities import EngineId, EntityId, Refusal, Slug, slug
from aidm.core.facts import Fact, traced
from aidm.core.io import FileStore, Library, decode
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import Answer, Exchange, Interjection, Line, Narration
from aidm.core.source import given_text
from aidm.core.tools import MasterTool
from aidm.core.views import PlayerView
from aidm.engines.base import Chattiness
from aidm.engines.registry import build_engines
from aidm.engines.seam import AnyEngine
from aidm.turn.context import render_interjection, render_narrator
from aidm.turn.run import NO_TURN, Turn

LOGGER = logging.getLogger(__name__)

# The prompt of a turn nobody played; the chat shows it as the story's own line.
OPENING_MARK = "(the story begins)"
STORY_MARK = "(the story goes on)"
INTERJECTION_MARK = "(the party speaks)"
MARKS = (OPENING_MARK, STORY_MARK, INTERJECTION_MARK)
# The faces of a d10 on which a member speaks after a turn.
INTERJECTION_ODDS: dict[Chattiness, int] = {"quiet": 1, "normal": 2, "chatty": 3}
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
REQUESTED = (
    "play stops here while the world is written on; end on this moment and settle nothing "
    "beyond what happened."
)
OPENING = (
    "The story begins here; the player has read nothing yet. Tell them, in the fiction and in "
    "this order: who they are (YOUR PARTY names them first) and where they stand; what is in "
    "front of them, the situation as they see it now; what they are here to do, from WHAT THIS "
    "SCENE IS ABOUT where it is given, said as the thing pulling at them; and two or three "
    "things they could plainly do first, offered by the place and the people, in prose, never "
    "as a list. Six to eight sentences. They have not acted, so settle nothing."
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
    interjections: bool = True
    rng: Random = field(default_factory=Random)
    phase: Role | None = None
    # The player's words for a write that opens no turn; the page shows them as their bubble.
    intent: str = ""
    turn: Turn | None = None
    # The party member speaking after the last turn; a new turn or a reload silences them.
    _speaking: Task[None] | None = field(default=None, repr=False)
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
                self.commit(self.engine.close(draft, OPENING_MARK, lines, ()))
            self._present()
        finally:
            self.phase = None

    async def play(self, answer: Answer) -> None:
        await self._turn(answer, self.state)

    async def act(self, action: Slug, words: str) -> None:
        if (ended := self.engine.over(self.state)) is not None:
            raise Refusal(f"{ended} The only way on is to restart.")
        if self.state.pending is not None:
            raise Refusal("the rules wait on the player's decision first")
        draft = self.state.draft()
        self.engine.act(draft, action, words)
        if draft.generation is None:
            await self._turn(Answer(text=words), draft)
            return
        self.intent = words
        try:
            self.commit(self.engine.commit(draft))
            written = await self._generate(words)
        finally:
            self.intent = ""
        if written:
            await self._turn(Answer(text=words), self.state)

    async def _turn(self, answer: Answer, state: AnyGame) -> None:
        self.hush()
        turn = Turn.begin(self.engine, state, answer, self.rng)
        self.turn, self.phase = turn, "master"
        try:
            # An answer that re-suspended leaves every tool refused: nothing for a master to do.
            if turn.draft.pending is None:
                await self._master(turn)
            lines: tuple[Line, ...] = ()
            if turn.narrates():
                self.phase = "narrator"
                lines = await self._narrate(turn.draft, tuple(turn.facts), turn.prompt, fatal=True)
            state = turn.finish(lines)
        finally:
            # Cleared before arrival: the tool surface must not reach a turn nobody plays.
            self.turn, self.phase = None, None
        self.commit(state)
        self._present()
        await self._generate()
        if (
            self.interjections
            and self.state.pending is None
            and self.engine.over(self.state) is None
        ):
            self._speaking = create_task(self.interject())
            self._retain(self._speaking)

    def hush(self) -> None:
        """Cancelling kills the narrator spawn: an answer nobody will read costs nothing more."""
        if self._speaking is not None:
            self._speaking.cancel()
            self._speaking = None

    async def interject(self) -> None:
        member = next(
            (
                candidate
                for candidate in self.engine.world(self.state).members()
                if self.rng.randint(1, 10) <= INTERJECTION_ODDS[candidate.chattiness]
            ),
            None,
        )
        if member is None:
            return
        history = self.engine.history(self.state)
        spoken = len(history)
        view = self.engine.narrator_view(self.state)
        evidence = traced(history[-1].facts if history else (), told_only=True)
        try:
            answer = await ask(
                self.spawner,
                "narrator",
                render_interjection(
                    view,
                    member.subject(),
                    member.rows(),
                    self.engine.scenes(self.state),
                    evidence,
                ),
                Interjection,
                partial(view.interjection_refusal, member.id),
            )
        except (OSError, Refusal) as failed:
            LOGGER.warning("the party did not speak: %s", failed)
            return
        if (
            self.turn is not None
            or self.phase is not None
            or len(self.engine.history(self.state)) != spoken
        ):
            LOGGER.info("%s's interjection came after the turn moved on; dropped", member.name)
            return
        if not answer.lines:
            return
        self.commit(
            self.engine.close(
                self.state.draft(), INTERJECTION_MARK, answer.lines, (), proposal=answer.proposal
            )
        )
        self.speak()

    async def _generate(self, prompt: str = STORY_MARK) -> bool:
        request = self.state.generation
        if request is None:
            return False
        draft = self.state.draft()
        draft.generation = None
        if self.engine.over(self.state) is not None:
            self.commit(self.engine.commit(draft))
            return False
        self.phase, grown = "worldsmith", True
        try:
            facts, telling = await self.engine.advance(draft, request, _worldsmith(self.spawner))
            if telling is None:
                self.commit(self.engine.commit(draft))
            else:
                self.phase = "narrator"
                lines = await self._narrate(draft, facts, telling, fatal=False)
                self.commit(self.engine.close(draft, prompt, lines, facts))
        except (OSError, Refusal) as failed:
            LOGGER.warning("the world did not grow: %s", failed)
            draft = self.state.draft()
            draft.generation = None
            self.commit(self.engine.close(draft, prompt, (), (UNWRITTEN,)))
            grown = False
        finally:
            self.phase = None
        self._present()
        return grown

    def _present(self) -> None:
        newest = self._newest()
        self.illustrate("" if newest is None else newest.narration)
        self.speak()

    async def _master(self, turn: Turn) -> None:
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
        if draft.generation is not None:
            evidence += f"\n- {REQUESTED}"
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
        self.hush()
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
        # The write was lost with the process: a reload never finds a request.
        state.generation = None
        return state


@dataclass(frozen=True, slots=True)
class RoleSpawner:
    """Each role goes where its settings send it: a CLI, or the builtin loop over an API."""

    settings: Settings
    cli: CliSpawner
    builtin: BuiltinSpawner

    async def run(self, role: Role, prompt: str, session: str | None) -> RunResult:
        config = self.settings.roles.for_name(role)
        played_by = self.cli if config.api is None else self.builtin
        return await played_by.run(role, prompt, session)


@dataclass(slots=True)
class Runtime:
    settings: Settings
    # A stub for tests; the runtime builds its own spawner because that spawner calls back into it.
    stub: InitVar[Spawner | None] = None
    spawner: Spawner = field(init=False)
    _sessions: dict[str, GameService] = field(default_factory=dict, repr=False)
    lock: Lock = field(default_factory=Lock, repr=False)
    engines: dict[EngineId, AnyEngine] = field(init=False)
    library: Library = field(init=False)
    store: FileStore = field(init=False)

    def __post_init__(self, stub: Spawner | None) -> None:
        self.engines = build_engines()
        self.spawner = self._spawner() if stub is None else stub
        self._mount()

    def _spawner(self) -> Spawner:
        settings = self.settings
        return RoleSpawner(settings, CliSpawner(settings), BuiltinSpawner(settings, self))

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

    def call(self, name: str, raw: Mapping[str, JsonValue]) -> str:
        """Between turns there is nothing to call."""
        playing = self.playing()
        turn = None if playing is None else playing.turn
        if turn is None:
            raise Refusal(NO_TURN)
        return turn.call(name, raw)

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
        self.spawner = self._spawner()
        self._mount()
        # An evicted session must not write: its member's answer would land on a rival's save.
        for session in self._sessions.values():
            session.hush()
        self._sessions.clear()

    async def new_scenario(
        self,
        engine_id: EngineId,
        meta: ScenarioMeta,
        document: Path | None,
        packs: Sequence[Slug],
        character_id: Slug,
    ) -> Slug:
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
            interjections=settings.interjections,
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
    return partial(ask, spawner, "worldsmith")
