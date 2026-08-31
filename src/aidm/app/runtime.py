import logging
from asyncio import Lock, Task, create_task
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from aidm.config import Settings, load_settings
from aidm.content.io import (
    FileStore,
    load_character,
    scenario_envelope,
    scenario_of,
    write_scenario,
)
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engines
from aidm.kernel.views import NarratorView, Views
from aidm.kits.scenes.source import given_text
from aidm.kits.scenes.worldsmith import apply_scene, opening_canon, scene_refusal
from aidm.state.entities import EngineId, EntityId, Slug, slug
from aidm.state.facts import Fact, told_traces, traced
from aidm.state.model import (
    Character,
    Game,
    Scenario,
    ScenarioMeta,
    ScenarioPayload,
    SceneWrite,
)
from aidm.state.play import Answer, Line, Narration
from aidm.turn.context import (
    CROSSING,
    render_master,
    render_narrator,
    render_opening,
    render_worldsmith,
    told_passages,
)
from aidm.turn.run import Turn, TurnStep, close_segment, speakers_refusal

from .launch import LaunchTarget
from .media import ICON_DIR, Illustrator
from .spawn import CliSpawner, Spawner

LOGGER = logging.getLogger(__name__)

NO_TURN = "no turn is open. The player starts one from the page; wait to be spawned again."
OFFERED = (
    "the player is choosing where to go; their answer opens the next scene. "
    "This turn is not over — finish what their action caused, then exit."
)
# What the crossing is filed under in the chronicle: the player took no action in it.
CROSSED = "(the story moves on)"


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
        """The turn: the game master's exit ends it, the narrator writes it, then it commits.
        `moving_on` is the player taking the way on, so `action` is what they mean to pursue."""
        if moving_on and not self.state.world.settled:
            raise ValueError("this scene has no way on yet; play it out first")

        def announce(step: TurnStep) -> None:
            self.step = step
            if on_step is not None:
                on_step(step)

        turn = Turn.begin(self.engine, self.state, action, self.rng, on_fact)
        self.turn, self.write_failure = turn, ""
        # The player named where they go; the worldsmith writes while the turn is still playing.
        if moving_on:
            self._write_scene(turn.prompt)
        try:
            announce("master")
            await self._act(turn)
            lines: tuple[Line, ...] = ()
            if turn.draft.pending is None or told_traces(turn.facts):
                announce("narrator")
                lines = await self._narrate(turn)
            state = turn.finish(lines)
        except BaseException:
            # The write's owner is dying; left alive it would install a scene on a later turn.
            self._abandon_write()
            raise
        finally:
            self.turn, self.step = None, None
        self.commit(state)
        self._illustrate(state.history[-1].narration)
        await self._cross_over(announce, turn.prompt)

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
        turn = self._playing()
        turn.started = True
        return turn.picture(self.settings.turn.recent_exchanges)

    def picture(self) -> str:
        return self._playing().picture(self.settings.turn.recent_exchanges)

    def offer_the_way_on(self) -> str:
        self._playing().offer_the_way_on()
        return OFFERED

    def _playing(self) -> Turn:
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
            await writing
            written, self._written = self._written, None
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
            lines = await self._narrate_arrival(draft, facts, pursuit)
            view = self.engine.views(draft).narrator
            self.commit(close_segment(view, draft, CROSSED, lines, facts))
        finally:
            self.step = None
        self._illustrate(self.state.history[-1].narration)

    async def _narrate_arrival(
        self, draft: Game, facts: tuple[Fact, ...], pursuit: str
    ) -> tuple[Line, ...]:
        view = self.engine.views(draft).narrator
        try:
            narration = await self.spawner.write(
                "narrator",
                render_narrator(
                    view,
                    evidence=traced(facts, told_only=True),
                    prompt=CROSSING.format(pursuit=pursuit),
                    passages=told_passages(draft, self.settings.turn.recent_exchanges),
                ),
                Narration,
                lambda written: _narration_refusal(view, written),
            )
        except (OSError, ValueError) as failed:
            # The scene cost minutes to write; an unwritable crossing must not throw it away.
            LOGGER.warning("the crossing went unnarrated: %s", failed)
            return ()
        return narration.lines

    def _abandon_write(self) -> None:
        """Cancelled, not just dropped: an awaited-by-nobody write still writes `_written`."""
        if self._writing is not None:
            _ = self._writing.cancel()
        self._writing, self._written = None, None

    def _write_scene(self, intent: str) -> None:
        self._abandon_write()
        # A deep copy, never the live state: the turn keeps playing while this runs.
        self._writing = create_task(self._write(self.state.draft(), intent))

    async def _write(self, snapshot: Game, intent: str) -> None:
        prompt = render_worldsmith(
            snapshot.world,
            snapshot.history,
            intent,
            self.engine.guidance(snapshot.packs),
            self.engine.sheet_rows(snapshot),
        )
        try:
            self._written = await self.spawner.write(
                "worldsmith",
                prompt,
                SceneWrite,
                lambda written: scene_refusal(written, snapshot.world),
            )
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
    # Companions cross by code, so nothing else would tell the narrator they came along.
    came = [draft.world.require(one).name for one in draft.world.companions]
    trace = f"the story moves to {written.title}"
    if came:
        trace += f", and {', '.join(came)} travels there with the player"
    opened = Fact(kind="scene_opened", trace=trace, told=True, card=f"New scene: {written.title}")
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
        character = load_character(self.settings.characters_dir, character_id, engine)
        source = given_text(premise, document, self.settings.source.max_chars)
        name = slug(title, self._scenario_ids())

        def written(scene: SceneWrite) -> Scenario:
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
                _ = begin_game(engine, name, written(scene), character)
            except ValueError as unplayable:
                return str(unplayable)
            return None

        scene = await self.spawner.write(
            "worldsmith", render_opening(source, engine.guidance(packs)), SceneWrite, refusal
        )
        write_scenario(self.settings.scenarios_dir, name, written(scene), document)
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
