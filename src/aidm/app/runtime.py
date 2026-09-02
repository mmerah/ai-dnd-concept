import logging
from asyncio import Lock, Task, create_task
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from random import Random

from pydantic import BaseModel

from aidm.config import Settings, load_settings
from aidm.core.entities import EngineId, EntityId, Slug, require_unique, slug
from aidm.core.facts import Fact, cards, traced
from aidm.core.io import FileStore, load_character, read_scenario, write_scenario
from aidm.core.model import AnyCharacter, AnyGame, AnyScenario, ScenarioKind
from aidm.core.play import Answer, Line, Narration
from aidm.core.source import given_text
from aidm.core.tools import MasterTool
from aidm.core.views import NarratorView, PlayerView
from aidm.engines.registry import begin_game, build_engines
from aidm.engines.seam import AnyEngine
from aidm.turn.context import MASTER, NARRATOR, render_master, render_narrator, told_passages
from aidm.turn.run import TURN_TOOLS, Turn, TurnStep, TurnTool, close_segment, narration_refusal

from .launch import LaunchTarget
from .media import Illustrator, open_illustrator
from .sessions import Conversations
from .spawn import CliSpawner, Spawner, answered

LOGGER = logging.getLogger(__name__)

# What a turn nobody played is filed under in the chronicle: the crossing, and the opening.
CROSSED = "(the story moves on)"
BEGUN = "(the story begins)"
OPENING = (
    "The story begins here; the player has read nothing yet. Tell them, in the fiction and in "
    "this order: who they are (WHO IS HERE names them first) and where they stand; what is in "
    "front of them, the situation as they see it now; what they are here to do, from WHAT THIS "
    "SCENE IS ABOUT, said as the thing pulling at them; and two or three things they could "
    "plainly do first, offered by the place and the people, in prose, never as a list. Six to "
    "eight sentences. They have not acted, so settle nothing."
)


@dataclass(frozen=True, slots=True)
class _Worldsmith:
    """The `WorldsmithAnswer` the platform hands an engine: one spawned role, one shared retry."""

    spawner: Spawner

    async def __call__[M: BaseModel](
        self, prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        return await answered(
            "worldsmith", prompt, model, refusal, partial(self.spawner.run, "worldsmith")
        )


@dataclass
class GameService:
    target: LaunchTarget
    scenario: AnyScenario
    character: AnyCharacter
    engine: AnyEngine
    spawner: Spawner
    store: FileStore
    sessions: Conversations
    settings: Settings
    media: Illustrator | None = None
    rng: Random = field(default_factory=Random)
    # A plain attribute, not a property: the play page binds its widgets to it.
    busy: bool = False
    step: TurnStep | None = None
    # The turn in flight; the tool surface reaches the live game through it.
    turn: Turn | None = None
    # Why the last scene write failed or would not fit; empty when none has.
    write_failure: str = ""
    _illustrations: set[Task[None]] = field(default_factory=set, repr=False)
    state: AnyGame = field(init=False)

    def __post_init__(self) -> None:
        saved = self.store.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(self.engine.restored(saved))

    @property
    def slug(self) -> str:
        return self.target.slug

    def unopened(self) -> bool:
        """No exchange yet: nobody has told the player where they stand."""
        return not self.busy and not self.engine.history(self.state)

    async def open(self, on_step: Callable[[TurnStep], None] | None = None) -> None:
        """A narrator that fails leaves the premise to do its work; a reload mid-opening is a
        no-op."""
        if not self.unopened():
            return
        announce = partial(self._announce, on_step=on_step)
        self.busy = True
        try:
            draft = self.state.draft()
            announce("narrator")
            lines = await self._narrate(draft, (), OPENING, fatal=False)
            if lines:
                view = self.engine.narrator_view(draft)
                self.commit(close_segment(self.engine, view, draft, BEGUN, lines, ()))
            else:
                # As in `play`: a narrator that remembers an opening that never landed is dropped.
                self.sessions.forget(self.slug)
            self.illustrate(_latest_narration(self.engine, self.state))
        finally:
            self.step, self.busy = None, False

    async def play(
        self,
        action: str | Answer,
        on_step: Callable[[TurnStep], None] | None = None,
        on_fact: Callable[[Fact], None] | None = None,
        *,
        moving_on: bool = False,
        on_commit: Callable[[], None] | None = None,
    ) -> None:
        """`moving_on` is the player taking the way on, so `action` is what they mean to pursue."""
        crossing = self.engine.crossing
        if moving_on and crossing is None:
            await self.extend(action, on_step=on_step)
            return
        if moving_on and not self.engine.ready(self.state):
            raise ValueError("the world offers no transition from here")
        announce = partial(self._announce, on_step=on_step)
        turn = Turn.begin(
            self.engine, self.state, action, self.rng, self.settings.recent_exchanges, on_fact
        )
        self.busy, self.turn, self.write_failure = True, turn, ""
        try:
            announce("master")
            await self._act(turn)
            lines: tuple[Line, ...] = ()
            if turn.draft.pending is None or any(fact.told for fact in turn.facts):
                announce("narrator")
                lines = await self._narrate(turn.draft, tuple(turn.facts), turn.prompt, fatal=True)
            state = turn.finish(lines)
            # Cleared before arrival: the tool surface must not reach a turn nobody plays.
            self.turn, self.step = None, None
            self.commit(state)
            if on_commit is not None:
                on_commit()
            self.illustrate(_latest_narration(self.engine, state))
            # The player named where they go; the worldsmith writes it once the turn is safe.
            if moving_on and crossing is not None and self.engine.over(state) is None:
                await self._grow(turn.prompt, announce, crossing.format(pursuit=turn.prompt))
                self.illustrate(_latest_narration(self.engine, self.state))
        except BaseException:
            # The turn is thrown away, so a role that remembers playing it must be too.
            self.sessions.forget(self.slug)
            raise
        finally:
            self.turn, self.step, self.busy = None, None, False

    async def extend(
        self,
        intent: str | Answer,
        on_step: Callable[[TurnStep], None] | None = None,
    ) -> None:
        """Author and install a region without a player turn; a told card is still filed."""
        if not self.engine.ready(self.state):
            raise ValueError("the world has no frontier to extend")
        if self.busy:
            raise ValueError("a turn is already in flight")
        if isinstance(intent, Answer):
            if intent.option_id is not None:
                raise ValueError("a transition needs written intent")
            intent_text = intent.text
        else:
            intent_text = intent
        announce = partial(self._announce, on_step=on_step)
        self.busy, self.write_failure = True, ""
        try:
            await self._grow(intent_text, announce, None)
        finally:
            self.step = None
            self.busy = False

    def _announce(self, step: TurnStep, on_step: Callable[[TurnStep], None] | None) -> None:
        self.step = step
        if on_step is not None:
            on_step(step)

    async def _act(self, turn: Turn) -> None:
        """A crashed game master still played the turn, if it applied anything legal first."""

        def nothing_landed() -> bool:
            return not turn.facts and turn.draft.pending is None

        try:
            await self.sessions.ask(
                self.slug,
                "master",
                MASTER + self.engine.instructions,
                render_master(self.engine.instructions, turn.prompt),
                cold_retry=nothing_landed,
            )
        except (OSError, ValueError) as failed:
            if nothing_landed():
                raise
            LOGGER.warning(
                "the game master failed after applying %d facts: %s", len(turn.facts), failed
            )

    async def _narrate(
        self, draft: AnyGame, facts: tuple[Fact, ...], prompt: str, *, fatal: bool
    ) -> tuple[Line, ...]:
        view = self.engine.narrator_view(draft)
        try:
            narration = await answered(
                "narrator",
                render_narrator(
                    view,
                    evidence=traced(facts, told_only=True),
                    prompt=prompt,
                    passages=told_passages(
                        self.engine.history(draft), self.settings.recent_exchanges
                    ),
                ),
                Narration,
                lambda written: narration_refusal(view, written),
                partial(self.sessions.ask, self.slug, "narrator", NARRATOR),
            )
        except (OSError, ValueError) as failed:
            if fatal:
                raise
            # The scene cost minutes to write; an unwritable arrival must not throw it away.
            LOGGER.warning("the arrival went unnarrated: %s", failed)
            return ()
        return narration.lines

    async def _grow(
        self, intent: str, announce: Callable[[TurnStep], None], brief: str | None
    ) -> None:
        announce("worldsmith")
        draft = self.state.draft()
        try:
            facts = await self.engine.advance(draft, intent, _Worldsmith(self.spawner))
            self.engine.validate(draft)
        except (OSError, ValueError) as failed:
            # Dropping the write costs a scene; raising costs the turn that was already played.
            self.write_failure = str(failed)
            LOGGER.warning("the world did not grow: %s", failed)
            return
        if brief is None and not cards(facts):
            self.commit(draft.committed())
            return
        prompt, lines = intent, ()  # a silent install's told card is filed under its intent
        if brief is not None:
            announce("narrator")
            prompt, lines = CROSSED, await self._narrate(draft, facts, brief, fatal=False)
        view = self.engine.narrator_view(draft)
        self.commit(close_segment(self.engine, view, draft, prompt, lines, facts))

    def player_view(self) -> PlayerView:
        return self.engine.player_view(self.state)

    def transition_available(self) -> bool:
        return self.engine.ready(self.state)

    def scene(self) -> NarratorView:
        return self.engine.narrator_view(self.state)

    def scene_art(self) -> Path | None:
        return None if self.media is None else self.media.scene_art(self.scene())

    def scene_pending(self) -> bool:
        return self.media is not None and self.media.scene_pending(self.scene())

    def icon(self, entity_id: EntityId) -> Path | None:
        return None if self.media is None else self.media.icon(entity_id)

    def illustrate(self, narration: str = "") -> None:
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
        self.sessions.forget(self.slug)
        self.state = opening
        self.write_failure = ""

    def commit(self, state: AnyGame) -> None:
        self.store.save(self.slug, state)
        self.state = state

    def _begun(self) -> AnyGame:
        return begin_game(self.engine, self.target.scenario_id, self.scenario, self.character)

    def _resumable(self, state: AnyGame) -> AnyGame:
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
    engines: dict[EngineId, AnyEngine] = field(init=False)

    def __post_init__(self) -> None:
        self.engines = build_engines(self.settings.packs_dir)

    def default_engine(self) -> EngineId:
        """Dict order picks it; a create page has to start somewhere."""
        return next(iter(self.engines))

    def published_tools(self) -> tuple[TurnTool | MasterTool[AnyGame], ...]:
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
        *,
        art_style: str,
        kind: ScenarioKind,
    ) -> Slug:
        """One worldsmith call authors the engine's complete opening world."""
        engine = self.engines[engine_id]
        character = load_character(
            self.settings.characters_dir, character_id, engine.id, engine.character
        )
        source = given_text(premise, document, self.settings.source_max_chars)
        name = slug(title, self._scenario_ids())

        def playable(built: AnyScenario) -> str | None:
            try:
                _ = begin_game(engine, name, built, character)
            except ValueError as unplayable:
                return str(unplayable)
            return None

        written = await engine.author(
            title, premise, source, packs, kind, _Worldsmith(self.spawner), playable
        )
        write_scenario(
            self.settings.scenarios_dir,
            name,
            written.model_copy(update={"art_style": art_style}),
            document,
        )
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
        scenario = read_scenario(
            settings.scenarios_dir,
            target.scenario_id,
            {engine_id: engine.scenario for engine_id, engine in self.engines.items()},
        )
        engine = self.engines[scenario.engine]
        character = load_character(
            settings.characters_dir, target.character_id, engine.id, engine.character
        )
        store = FileStore(settings.saves_dir)
        return GameService(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            spawner=self.spawner,
            store=store,
            sessions=Conversations(self.spawner, store, settings),
            settings=settings,
            media=open_illustrator(
                settings, target, store, style=scenario.art_style or engine.art_style
            ),
        )


def _latest_narration(engine: AnyEngine, state: AnyGame) -> str:
    history = engine.history(state)
    return history[-1].narration if history else ""
