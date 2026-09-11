import logging
from asyncio import Task, create_task
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.app.launch import LaunchTarget
from aidm.app.media import ICON_DIR, Illustrator, open_illustrator
from aidm.app.roles import RoleRunner, Roles
from aidm.app.spawn import Spawner, worldsmith
from aidm.app.speech import Reader, open_reader
from aidm.config import Role, Settings, read_settings
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.io import FileStore, Library, decode
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario, ScenarioMeta
from aidm.core.play import Answer, Exchange, Mark, SpokenLine
from aidm.core.source import given_text
from aidm.core.tools import MasterTool
from aidm.core.views import PlayerView
from aidm.engines.base import Chattiness, Person
from aidm.engines.registry import build_engines
from aidm.engines.seam import AnyEngine
from aidm.turn.run import NO_TURN, Turn

LOGGER = logging.getLogger(__name__)

# The faces of a d10 on which a member speaks after a turn.
INTERJECTION_ODDS: dict[Chattiness, int] = {"quiet": 1, "normal": 2, "chatty": 3}
OPENING_NARRATION = (
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
    roles: Roles
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
        saved = self.store.read(self.slug)
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

    @property
    def presents(self) -> bool:
        return self.media is not None or self.reader is not None

    def unopened(self) -> bool:
        return not self.busy and not self.state.exchanges()

    async def open(self) -> None:
        """A failed narrator leaves the premise to do its work; a reload mid-opening is a no-op."""
        if not self.unopened():
            return
        self.phase = "narrator"
        try:
            draft = self.state.draft()
            lines = await self.roles.narrate(self.engine, draft, (), OPENING_NARRATION, fatal=False)
            if lines:
                self.save(self.engine.close(draft, lines, (), mark="opening"))
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
            self.save(self.engine.land(draft))
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
                await self.roles.master(turn)
            lines: tuple[SpokenLine, ...] = ()
            if turn.narrates():
                self.phase = "narrator"
                lines = await self.roles.narrate(
                    self.engine, turn.draft, tuple(turn.facts), turn.words, fatal=True
                )
            state = turn.finish(lines)
        finally:
            # Cleared before arrival: the tool surface must not reach a turn nobody plays.
            self.turn, self.phase = None, None
        self.save(state)
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
                if self._speaks(candidate)
            ),
            None,
        )
        if member is None:
            return
        before = self.state
        try:
            lines, proposal = await self.roles.interject(self.engine, self.state, member)
        except (OSError, Refusal) as failed:
            LOGGER.warning("the party did not speak: %s", failed)
            return
        if self.turn is not None or self.phase is not None or self.state is not before:
            LOGGER.info("%s's interjection came after the turn moved on; dropped", member.name)
            return
        if not lines:
            return
        self.save(
            self.engine.close(self.state.draft(), lines, (), mark="interjection", proposal=proposal)
        )
        self.speak(self._newest())

    def _speaks(self, candidate: Person) -> bool:
        # The one die that is not the game's: it spawns a narrator, changes no state, lands no fact.
        return self.rng.randint(1, 10) <= INTERJECTION_ODDS[candidate.chattiness]

    async def _generate(self, words: str = "") -> bool:
        request = self.state.generation
        if request is None:
            return False
        draft = self.state.draft()
        draft.generation = None
        if self.engine.over(self.state) is not None:
            self.save(self.engine.land(draft))
            return False
        mark: Mark = "" if words else "story"
        self.phase, grown = "worldsmith", True
        try:
            facts, telling = await self.engine.advance(
                draft, request, worldsmith(self.roles.spawner)
            )
            if telling is None:
                self.save(self.engine.land(draft))
            else:
                self.phase = "narrator"
                lines = await self.roles.narrate(self.engine, draft, facts, telling, fatal=False)
                self.save(self.engine.close(draft, lines, facts, words=words, mark=mark))
        except (OSError, Refusal) as failed:
            LOGGER.warning("the world did not grow: %s", failed)
            draft = self.state.draft()
            draft.generation = None
            self.save(
                self.engine.close(
                    draft,
                    (),
                    (self.engine.requests[request.operation].unwritten,),
                    words=words,
                    mark=mark,
                )
            )
            grown = False
        finally:
            self.phase = None
        self._present()
        return grown

    def _present(self) -> None:
        newest = self._newest()
        self.illustrate("" if newest is None else newest.narration)
        self.speak(newest)

    def player_view(self) -> PlayerView:
        return self.engine.player_view(self.state)

    def history(self) -> tuple[Exchange, ...]:
        return self.state.exchanges()

    def scene_art(self) -> Path | None:
        if self.media is None:
            return None
        return self.media.scene_art(self.engine.narrator_view(self.state))

    def icon(self, entity_id: Slug) -> Path | None:
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

    def speak(self, newest: Exchange | None) -> None:
        if self.reader is None or newest is None:
            return
        self._retain(create_task(self.reader.read(newest)))

    def _newest(self) -> Exchange | None:
        history = self.state.exchanges()
        return history[-1] if history else None

    def _retain(self, task: Task[None]) -> None:
        """Retain background tasks because asyncio may collect unreferenced tasks early."""
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    def stop(self) -> None:
        self.hush()
        for task in self._background:
            task.cancel()

    def restart(self) -> None:
        self.hush()
        opening = self._begin()
        self.store.discard(self.slug)
        self.state = opening

    def save(self, state: AnyGame) -> None:
        self.store.write(self.slug, state)
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
    settings: Settings
    spawner: Spawner
    _sessions: dict[str, GameService] = field(default_factory=dict, repr=False)
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
        turn = self.playing()
        return () if turn is None else turn.published_tools()

    def playing(self) -> Turn | None:
        turns = (session.turn for session in self._sessions.values())
        return next((turn for turn in turns if turn is not None), None)

    def call(self, name: str, raw: JsonValue) -> str:
        turn = self.playing()
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
        self.spawner = RoleRunner(self.settings)
        self._mount()
        # A late answer or image from an evicted session would land where the new session reads.
        for session in self._sessions.values():
            session.stop()
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

        def check(built: AnyScenario) -> None:
            engine.begin(name, built, character)

        scenario = await engine.author(meta, source, packs, worldsmith(self.spawner), check)
        self.library.write_scenario(name, scenario)
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
            roles=Roles(self.spawner),
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
