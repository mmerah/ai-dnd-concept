import logging
from asyncio import Lock, Task, create_task
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from aidm.config import Settings, load_settings
from aidm.content.io import FileStore, load_character, scenario_envelope, scenario_of
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engines
from aidm.kernel.views import NarratorView, Views
from aidm.kits.scenes.boundary import scene_spent
from aidm.kits.scenes.worldsmith import apply_scene, scene_unmet
from aidm.state.entities import EngineId, EntityId
from aidm.state.facts import Fact, told_traces, traced
from aidm.state.model import Character, Game, Scenario, SceneWrite
from aidm.state.play import Answer, Line, Narration
from aidm.turn.context import render_master, render_narrator, render_worldsmith, told_passages
from aidm.turn.run import Turn, TurnStep, speakers_refusal

from .launch import LaunchTarget
from .media import ICON_DIR, Illustrator
from .spawn import CliSpawner, Spawner

LOGGER = logging.getLogger(__name__)

NO_TURN = "no turn is open. The player starts one from the page; wait to be spawned again."
WRITING = (
    "the worldsmith is writing the next scene; it arrives on a later turn. "
    "This turn is not over — finish what the player's action caused, then exit."
)
# A scene written more turns ago than this describes a world the player has already left.
STALE_AFTER = 1


def open_media(
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
    busy: bool = False
    step: TurnStep | None = None
    # The turn in flight; the tool surface reaches the live game through it.
    turn: Turn | None = None
    # The game master's whole output, raw, for the dev tab; one spawn, so one string.
    master_log: str = ""
    # Why the last scene write failed or would not fit; empty when none has.
    write_failure: str = ""
    _illustrations: set[Task[None]] = field(default_factory=set, repr=False)
    _writing: Task[None] | None = field(default=None, repr=False)
    _written: SceneWrite | None = field(default=None, repr=False)
    _written_at: int = 0
    _write_intent: str = ""
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
    ) -> None:
        """The turn: the game master's exit ends it, the narrator writes it, then it commits."""

        def announce(step: TurnStep) -> None:
            self.step = step
            if on_step is not None:
                on_step(step)

        turn = Turn.begin(self.engine, self.state, action, self.rng, on_fact)
        self.turn = turn
        try:
            announce("master")
            await self._act(turn)
            lines: tuple[Line, ...] = ()
            if turn.draft.pending is None or told_traces(turn.facts):
                announce("narrator")
                lines = await self._narrate(turn)
            state = turn.finish(lines)
        finally:
            self.turn, self.step = None, None
        self.commit(state)
        self._illustrate(state.history[-1].narration)
        self._speculate()

    async def _act(self, turn: Turn) -> None:
        """A crashed game master still played the turn, if it applied anything legal first."""
        self.master_log = ""
        try:
            self.master_log = await self.spawner.act(
                render_master(self.engine.instructions, turn.prompt)
            )
        except (OSError, ValueError) as failed:
            if not turn.facts and turn.draft.pending is None:
                raise
            LOGGER.warning(
                "the game master failed after applying %d facts: %s", len(turn.facts), failed
            )

    async def _narrate(self, turn: Turn) -> tuple[Line, ...]:
        view = self.engine.views(turn.draft).narrator
        narration = await self.spawner.write(
            "narrator",
            render_narrator(
                view,
                evidence=traced(turn.facts, told_only=True),
                prompt=turn.prompt,
                passages=told_passages(turn.draft, self.settings.turn.recent_exchanges),
            ),
            Narration,
            lambda written: _narration_refusal(view, written),
        )
        return narration.lines

    def start_turn(self) -> str:
        """The scene the worldsmith wrote is installed here, so the picture already holds it."""
        turn = self._playing()
        self._install_scene(turn)
        turn.started = True
        return self.picture()

    def picture(self) -> str:
        return self._playing().picture(self.settings.turn.recent_exchanges)

    def begin_next_scene(self, intent: str, include: Sequence[str]) -> str:
        self._write_scene(intent, include)
        return WRITING

    def _playing(self) -> Turn:
        turn = self.turn
        if turn is None:
            raise ValueError(NO_TURN)
        return turn

    def _install_scene(self, turn: Turn) -> None:
        written, self._written = self._written, None
        if written is None:
            return
        if turn.draft.turn - self._written_at > STALE_AFTER:
            # Discarded and rewritten: a worldsmith slower than the player would else never land.
            LOGGER.info("rewriting a scene written for turn %d", self._written_at)
            self._write_scene(self._write_intent, ())
            return
        try:
            _ = turn.apply(lambda draft, _rng: _installed(self.engine, draft, written))
        except ValueError as refused:
            # The snapshot moved under the scene; dropping it costs a scene, raising costs the turn.
            self.write_failure = str(refused)
            LOGGER.warning("the written scene no longer fits the world: %s", refused)

    def _speculate(self) -> None:
        """Start the write before the game master asks: the wait was being spent anyway."""
        reason = scene_spent(self.state)
        if reason is None or self._written is not None or self._writing_now():
            return
        self._write_scene(reason, ())

    def _writing_now(self) -> bool:
        return self._writing is not None and not self._writing.done()

    def _write_scene(self, intent: str, include: Sequence[str]) -> None:
        if self._writing_now():
            if self._write_intent == intent:
                return
            # A speculative draft the game master's own intent supersedes is worth nothing.
            _ = self._writing and self._writing.cancel()
        self._written, self._write_intent, self.write_failure = None, intent, ""
        # A deep copy, never the live state: the player may take another turn while this runs.
        task = create_task(self._write(self.state.draft(), intent, tuple(include)))
        self._writing = task

    async def _write(self, snapshot: Game, intent: str, include: tuple[str, ...]) -> None:
        def unmet(written: SceneWrite) -> str | None:
            missing = scene_unmet(written, snapshot.world, opening=False)
            return None if not missing else "the scene needs " + "; ".join(missing)

        prompt = render_worldsmith(
            snapshot.world,
            intent,
            include,
            self.engine.guidance(snapshot),
            self.engine.sheet_rows(snapshot),
        )
        try:
            self._written = await self.spawner.write("worldsmith", prompt, SceneWrite, unmet)
            self._written_at = snapshot.turn
        except (OSError, ValueError) as failed:
            self.write_failure = str(failed)
            LOGGER.warning("the worldsmith wrote no scene: %s", failed)

    def view(self) -> Views:
        return self.engine.views(self.state)

    def scene(self) -> NarratorView:
        return self.view().narrator

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
        task = create_task(self.media.illustrate(self.view(), narration))
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


def _narration_refusal(view: NarratorView, written: Narration) -> str | None:
    if not written.text:
        return "write the narration lines: an empty answer shows the player nothing."
    return speakers_refusal(view, written.lines)


def _installed(engine: Engine, draft: Game, written: SceneWrite) -> tuple[Fact, ...]:
    """What the rules settle as the old scene ends, then the new scene itself."""
    closed = engine.scene_closed(draft)
    # A deep copy: the trial run and the real one must not share the entities the scene brings.
    apply_scene(draft.world, written.model_copy(deep=True), draft.turn)
    opened = Fact(
        kind="scene_opened",
        trace=f"the story moves to {written.title}",
        told=True,
        card=f"New scene: {written.title}",
    )
    return (*closed, opened)


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
        """One process owns the game and turns are sequential, so at most one is in flight."""
        return next((one for one in self._sessions.values() if one.turn is not None), None)

    def busy_refusal(self) -> str | None:
        """Evicting a session mid-turn would let the next tab open a rival writer on that save."""
        playing = [slug for slug, session in self._sessions.items() if session.busy]
        return f"A turn is in flight in {playing[0]!r}." if playing else None

    def reload_settings(self) -> None:
        self.settings = load_settings()
        self.engines = build_engines(self.settings.packs_dir)
        self.spawner = CliSpawner(self.settings)
        self._sessions.clear()

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
        scenario = scenario_of(envelope, engine)
        character = load_character(settings.characters_dir, target.character_id, engine)
        store = FileStore(settings.saves_dir)
        return GameService(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            spawner=self.spawner,
            store=store,
            settings=settings,
            media=open_media(settings, target, scenario, character, store),
        )
