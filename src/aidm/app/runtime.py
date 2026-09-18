import logging
from asyncio import CancelledError, Task, create_task, gather, to_thread
from collections.abc import AsyncGenerator, Coroutine, Iterable, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import Any

from aidm.app.launch import LauncherCatalog, LaunchTarget, check_resumes
from aidm.app.present import ICON_DIR, Presenter
from aidm.app.providers import close_client
from aidm.app.roles import (
    OPENING_NARRATION,
    run_interjection,
    run_master,
    run_narrator,
    worldsmith_answer,
)
from aidm.app.spawn import RoleRunner, Spawner
from aidm.config import Role, Settings
from aidm.core.entities import EngineId, Refusal, Slug, slug
from aidm.core.facts import Fact
from aidm.core.io import FileStore, Library, PackStore
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario, ScenarioMeta
from aidm.core.play import Answer, Exchange, Mark, SpokenLine
from aidm.core.source import given_text
from aidm.core.views import Chattiness, PlayerView
from aidm.engines.engine import AnyEngine
from aidm.engines.packs import SRD_PACK
from aidm.engines.registry import build_engines
from aidm.turn import NO_TURN, RESTART, Turn

LOGGER = logging.getLogger(__name__)

# The faces of a d10 on which a member speaks after a turn.
INTERJECTION_ODDS: dict[Chattiness, int] = {"quiet": 1, "normal": 2, "chatty": 3}
IN_FLIGHT_HERE = "A turn is already in flight in this game."
IN_FLIGHT_ELSEWHERE = "Another game is taking a turn. Wait for it to finish, then try again."


@dataclass(slots=True)
class Tasks:
    running: set[Task[None]] = field(default_factory=set)

    def retain(self, task: Task[None]) -> None:
        """Retained because asyncio may collect an unreferenced task early."""
        self.running.add(task)
        task.add_done_callback(self._done)

    async def settled(self) -> None:
        """The test hook: every background task this service started has landed."""
        with suppress(CancelledError):
            await gather(*self.running)

    async def close(self) -> None:
        tasks = list(self.running)
        for task in tasks:
            task.cancel()
        await gather(*tasks, return_exceptions=True)

    def _done(self, task: Task[None]) -> None:
        self.running.discard(task)
        if task.cancelled():
            return
        if (failed := task.exception()) is not None:
            LOGGER.exception("background task failed", exc_info=failed)


@dataclass(slots=True, kw_only=True)
class GameService:
    target: LaunchTarget
    scenario: AnyScenario
    character: AnyCharacter
    engine: AnyEngine
    spawner: Spawner
    store: FileStore
    state: AnyGame
    gate: "Gate" = field(repr=False, compare=False)
    presenter: Presenter
    interjections: bool = True
    meanwhile: bool = True
    rng: Random = field(default_factory=Random)
    chatter: Random = field(default_factory=Random)
    working_role: Role | None = None
    # The player's words for a write that opens no turn; the page shows them as their bubble.
    intent: str = ""
    turn: Turn | None = None
    # The party member speaking after the last turn; a new turn or a reload silences them.
    _speaking: Task[None] | None = field(default=None, repr=False)
    tasks: Tasks = field(default_factory=Tasks, repr=False)

    @property
    def slug(self) -> str:
        return self.target.slug

    @property
    def speaking(self) -> bool:
        return self._speaking is not None and not self._speaking.done()

    @property
    def unopened(self) -> bool:
        return self.working_role is None and not self.state.exchanges()

    @asynccontextmanager
    async def working(self, role: Role) -> AsyncGenerator[None]:
        self.working_role = role
        try:
            yield
        finally:
            self.working_role = None

    async def open(self) -> None:
        """A failed narrator saves nothing: the premise is what the player reads."""
        # A second tab's timer must not run the page reset over an opening already in flight.
        if not self.unopened:
            return
        async with self.gate.admit(self), self.working("narrator"):
            draft = self.state.draft()
            lines = await self._narrated(draft, (), OPENING_NARRATION)
            if lines:
                self.save(self.engine.close(draft, lines, (), mark="opening"))
            self.present()

    async def play(self, answer: Answer) -> None:
        async with self.gate.admit(self):
            await self._turn(answer, self.state)

    async def act(self, action_id: Slug, words: str) -> None:
        async with self.gate.admit(self):
            self.hush()
            if (ended := self.engine.ending(self.state)) is not None:
                raise Refusal(f"{ended} {RESTART}")
            if self.state.pending is not None:
                raise Refusal("the rules wait on the player's decision first")
            draft = self.state.draft()
            self.engine.act(draft, action_id, words)
            if draft.commission is None:
                await self._turn(Answer(text=words), draft)
                return
            self.intent = words
            try:
                self.save(self.engine.accept(draft))
                written = await self._write_commission(words=words, mark="")
            finally:
                self.intent = ""
            if written:
                await self._turn(Answer(text=words), self.state)

    async def _turn(self, answer: Answer, state: AnyGame) -> None:
        self.hush()
        turn = Turn.begin(self.engine, state, answer, self.rng)
        self.turn = turn
        try:
            async with self.working("master"):
                if turn.played:
                    await run_master(self.spawner, turn)
            lines: tuple[SpokenLine, ...] = ()
            if turn.narrates:
                async with self.working("narrator"):
                    lines = await self._narrated(
                        turn.draft, tuple(turn.facts), turn.words, landed=turn.landed
                    )
            state = turn.finish(lines, enabled=self.meanwhile)
        finally:
            # Cleared before arrival: the tool surface must not reach a turn nobody plays.
            self.turn = None
        self.save(state)
        self.rng.setstate(turn.rng.getstate())
        self.present()
        await self._write_commission(words="", mark="story")
        if (
            self.interjections
            and self.state.pending is None
            and self.engine.ending(self.state) is None
        ):
            self._speaking = create_task(self.let_party_speak())
            self.tasks.retain(self._speaking)

    def hush(self) -> None:
        """Cancelling kills the narrator spawn: an answer nobody will read costs nothing more."""
        if self._speaking is not None:
            self._speaking.cancel()
            self._speaking = None

    async def let_party_speak(self) -> None:
        member = next(
            (
                candidate
                for candidate in self.engine.companions(self.state)
                # Not the game's die: it spawns a narrator, changes no state, lands no fact.
                if self.chatter.randint(1, 10) <= INTERJECTION_ODDS[candidate.chattiness]
            ),
            None,
        )
        if member is None:
            return
        before = self.state
        try:
            lines, proposal = await run_interjection(self.spawner, self.engine, self.state, member)
        except Refusal as failed:
            LOGGER.warning("the party did not speak: %s", failed)
            return
        if self.turn is not None or self.working_role is not None or self.state is not before:
            LOGGER.info("%s's interjection came after the turn moved on; dropped", member.name)
            return
        if not lines:
            return
        self.save(
            self.engine.close(self.state.draft(), lines, (), mark="interjection", proposal=proposal)
        )
        self._launch(self.presenter.speak(self._newest()))

    async def _write_commission(self, *, words: str, mark: Mark) -> bool:
        commission = self.state.commission
        if commission is None:
            return False
        draft = self.state.draft()
        draft.commission = None
        if self.engine.ending(self.state) is not None:
            self.save(self.engine.accept(draft))
            return False
        grown = True
        try:
            async with self.working("worldsmith"):
                written = await self.engine.advance(
                    draft, commission, worldsmith_answer(self.spawner)
                )
            if written.narrator_prompt is None:
                landed = self.engine.accept(draft)
            else:
                async with self.working("narrator"):
                    lines = await self._narrated(draft, written.facts, written.narrator_prompt)
                landed = self.engine.close(draft, lines, written.facts, words=words, mark=mark)
        except Refusal as failed:
            LOGGER.warning("the world did not grow: %s", failed)
            draft = self.state.draft()
            draft.commission = None
            failure_fact = self.engine.operations()[commission.operation].failure_fact
            landed = self.engine.close(draft, (), (failure_fact,), words=words, mark=mark)
            grown = False
        self.save(landed)
        self.present()
        return grown

    async def _narrated(
        self, draft: AnyGame, facts: tuple[Fact, ...], prompt: str, *, landed: bool = True
    ) -> tuple[SpokenLine, ...]:
        """Nothing landed means nothing to save, so the player hears why and keeps their words."""
        try:
            return await run_narrator(self.spawner, self.engine, draft, facts, prompt)
        except Refusal as failed:
            if not landed:
                raise
            LOGGER.warning("the turn went unnarrated: %s", failed)
            return ()

    def present(self, *, spoken: bool = True) -> None:
        """`spoken=False` is the page build: a cached clip never autoplays on a load."""
        if not self.presenter.enabled:
            return
        view = self.engine.narrator_view(self.state)
        newest = self._newest() if spoken else None
        self._launch(self.presenter.present(view, self.player_view().player, newest))

    def player_view(self) -> PlayerView:
        return self.engine.player_view(self.state)

    def scene_art(self) -> Path | None:
        return self.presenter.illustrator.scene_art(self.engine.narrator_view(self.state))

    def icon(self, entity_id: Slug) -> Path | None:
        return self.presenter.illustrator.icon(entity_id)

    def newest_clip(self) -> Path | None:
        newest = self._newest()
        return None if newest is None else self.presenter.reader.clip(newest)

    async def close(self) -> None:
        self.hush()
        await self.tasks.close()

    async def restart(self) -> None:
        async with self.gate.admit(self):
            self.hush()
            opening = self.engine.begin(self.target.scenario_id, self.scenario, self.character)
            self.store.discard(self.slug)
            self.state = opening

    def save(self, state: AnyGame) -> None:
        self.store.write(self.slug, state)
        self.state = state

    def _newest(self) -> Exchange | None:
        history = self.state.exchanges()
        return history[-1] if history else None

    def _launch(self, coroutines: Iterable[Coroutine[Any, Any, None]]) -> None:
        for coroutine in coroutines:
            self.tasks.retain(create_task(coroutine))


class Busy(Refusal):
    def __init__(self, *, elsewhere: bool) -> None:
        super().__init__(IN_FLIGHT_ELSEWHERE if elsewhere else IN_FLIGHT_HERE)
        self.elsewhere = elsewhere


@dataclass(slots=True)
class Gate:
    admitted: GameService | None = field(default=None, repr=False)

    @property
    def turn(self) -> Turn | None:
        return None if self.admitted is None else self.admitted.turn

    def require_turn(self) -> Turn:
        """A tool call between turns is refused, not a crash: nobody is playing one."""
        if (turn := self.turn) is None:
            raise Refusal(NO_TURN)
        return turn

    @asynccontextmanager
    async def admit(self, session: GameService) -> AsyncGenerator[None]:
        """One writer at a time: two turns on one save is the only failure that costs a game."""
        if self.admitted is not None:
            raise Busy(elsewhere=self.admitted is not session)
        self.admitted = session
        try:
            yield
        finally:
            self.admitted = None


class Runtime:
    def __init__(self, settings: Settings, spawner: Spawner | None = None) -> None:
        self.settings = settings
        self.spawner: Spawner = spawner or RoleRunner(settings)
        self.gate = Gate()
        self.engines = build_engines(settings.packs_dir)
        self.library = Library(settings.scenarios_dir, settings.characters_dir)
        self.store = FileStore(settings.saves_dir)
        self.packs = PackStore(settings.packs_dir)
        self._sessions: dict[str, GameService] = {}

    @property
    def default_engine(self) -> EngineId:
        return next(iter(self.engines))

    @property
    def default_pack(self) -> Slug:
        """Every engine ships it, so the create pages start there."""
        return SRD_PACK

    async def close(self) -> None:
        for session in list(self._sessions.values()):
            await session.close()
        await close_client()

    def catalog(self) -> LauncherCatalog:
        return LauncherCatalog.read(self.library, self.store, self.engines)

    def engine(self, engine_id: EngineId) -> AnyEngine:
        found = self.engines.get(engine_id)
        if found is None:
            raise Refusal(f"no rules {engine_id!r}")
        return found

    def engine_options(self) -> dict[EngineId, str]:
        return {engine.id: engine.title for engine in self.engines.values()}

    def pack_boxes(self, engine_id: EngineId, pack_id: Slug) -> tuple[str, bool, dict[str, str]]:
        """The pack's name, whether the player may write it, and every field as text."""
        packs = self.engine(engine_id).packs
        pack = packs.require(pack_id)
        return pack.name, pack_id in packs.written, pack.boxes()

    async def new_scenario(
        self,
        engine_id: EngineId,
        meta: ScenarioMeta,
        document: Path | None,
        pack_id: Slug,
        character_id: Slug,
    ) -> Slug:
        engine = self.engines[engine_id]
        character = self.library.read_character(character_id, engine.id, engine.character)
        engine.packs.require(pack_id)
        source = await to_thread(given_text, meta.premise, document)
        name = slug(meta.title, self.library.scenario_ids())

        def check(built: AnyScenario) -> None:
            engine.begin(name, built, character)

        scenario = await engine.author(
            meta, source, pack_id, worldsmith_answer(self.spawner), check
        )
        self.library.write_scenario(name, scenario)
        LOGGER.info("scenario written: slug=%s title=%r", name, meta.title)
        return name

    async def new_pack(
        self, engine_id: EngineId, name: str, premise: str, document: Path | None, license: str
    ) -> Slug:
        """Written and installed only once both asks land, so a failed pack leaves no file."""
        engine = self.engines[engine_id]
        source = await to_thread(given_text, premise, document)
        pack_id = slug(name, (*engine.packs.installed, *self.packs.ids(engine.id)))
        origin = (
            "written in this app from the premise"
            if document is None
            else f"written in this app from {document.name}"
        )
        pack = await engine.pack_author.author(
            name=name,
            source=source,
            origin=origin,
            license=license,
            worldsmith=worldsmith_answer(self.spawner),
        )
        self.packs.write(engine.id, pack_id, pack)
        engine.install_pack(pack_id, pack)
        LOGGER.info("pack written: engine=%s slug=%s name=%r", engine.id, pack_id, name)
        return pack_id

    def rewrite_pack(self, engine_id: EngineId, pack_id: Slug, values: Mapping[str, str]) -> None:
        """The page's edits, parsed and rebuilt, on disk and in the running engine at once."""
        engine = self.engine(engine_id)
        pack = engine.packs.require(pack_id)
        if pack_id not in engine.packs.written:
            raise Refusal("shipped packs are read-only")
        rebuilt = engine.pack_author.edited(pack, values)
        self.packs.write(engine.id, pack_id, rebuilt)
        engine.install_pack(pack_id, rebuilt)
        LOGGER.info("pack rewritten: engine=%s slug=%s", engine.id, pack_id)

    def session(self, target: LaunchTarget) -> GameService:
        """Memoised: a page render must not rebuild the game and drop the turn in flight."""
        if target.slug not in self._sessions:
            self._sessions[target.slug] = self._open(target)
        return self._sessions[target.slug]

    def _resumed(
        self,
        engine: AnyEngine,
        target: LaunchTarget,
        scenario: AnyScenario,
        character: AnyCharacter,
    ) -> AnyGame:
        saved = self.store.read(target.slug)
        if saved is None:
            state = engine.begin(target.scenario_id, scenario, character)
        else:
            state = engine.restore(saved)
            check_resumes(state, target, scenario.meta)
        # A save armed before the switch went off must not spend itself on the next write.
        if not self.settings.meanwhile:
            engine.disarm(state)
        return state

    def _open(self, target: LaunchTarget) -> GameService:
        settings = self.settings
        models = {engine_id: engine.scenario for engine_id, engine in self.engines.items()}
        scenario = self.library.read_scenario(target.scenario_id, models)
        engine = self.engines[scenario.engine]
        character = self.library.read_character(target.character_id, engine.id, engine.character)
        return GameService(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            spawner=self.spawner,
            store=self.store,
            state=self._resumed(engine, target, scenario, character),
            gate=self.gate,
            interjections=settings.interjections,
            meanwhile=settings.meanwhile,
            presenter=Presenter.open(
                settings,
                self.store,
                target.slug,
                style=scenario.meta.art_style or engine.art_style,
                icon_dirs=(
                    self.library.scenario_folder(target.scenario_id) / ICON_DIR,
                    self.library.character_folder(target.character_id) / ICON_DIR,
                ),
                voice=scenario.meta.voice or settings.speech.voice,
            ),
        )
