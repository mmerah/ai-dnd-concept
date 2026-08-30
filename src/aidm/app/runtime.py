from asyncio import Task, create_task
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from aidm.config import Settings, load_settings
from aidm.content.io import FileStore, load_character, scenario_envelope, scenario_of
from aidm.engines.core import Engine
from aidm.engines.registry import begin_game, build_engines
from aidm.kernel.views import NarratorView, Views
from aidm.kits.scenes.boundary import scene_spent
from aidm.state.entities import EngineId, EntityId
from aidm.state.facts import Fact
from aidm.state.model import Character, Game, Scenario
from aidm.state.play import Answer, Line
from aidm.turn.run import Turn, TurnAgents, TurnStep, build_turn_agents, run_segment

from .launch import LaunchTarget
from .media import ICON_DIR, Illustrator


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
    stages: TurnAgents | None
    store: FileStore
    settings: Settings
    media: Illustrator | None = None
    rng: Random = field(default_factory=Random)
    busy: bool = False
    step: TurnStep | None = None
    _illustrations: set[Task[None]] = field(default_factory=set, repr=False)
    state: Game = field(init=False)
    _stamp: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._stamp = self.store.stamp(self.slug)
        saved = self.store.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(self.engine.restored(saved))

    @property
    def slug(self) -> str:
        return self.target.slug

    def begin_turn(
        self,
        player_input: str | Answer,
        on_fact: Callable[[Fact], None] | None = None,
    ) -> Turn:
        """Code mode commits per accepted call; builtin commits once when the segment ends."""
        commit: Callable[[Game], None] = (
            (lambda draft: self.commit(draft.committed()))
            if self.settings.code_mode
            else (lambda _: None)
        )
        return Turn.begin(self.engine, self.state, player_input, self.rng, commit, on_fact)

    def end_turn(self, turn: Turn, lines: tuple[Line, ...]) -> Game:
        state = turn.finish(lines)
        self.commit(state)
        return state

    async def submit(
        self,
        player_input: str | Answer,
        on_step: Callable[[TurnStep], None] | None = None,
        on_fact: Callable[[Fact], None] | None = None,
    ) -> None:
        """Commit only after the full segment succeeds."""
        if self.stages is None:
            raise ValueError("code mode plays the turn in the MCP server, not here")
        turn = self.begin_turn(player_input, on_fact)
        lines = await run_segment(turn, stages=self.stages, settings=self.settings, on_step=on_step)
        state = self.end_turn(turn, lines)
        self._illustrate(state.history[-1].narration)

    def scene_spent(self) -> str | None:
        return scene_spent(self.state)

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
        self._stamp = self.store.stamp(self.slug)

    def reload(self) -> bool:
        """Code mode plays the turn in another process; the viewer re-reads what that committed."""
        stamp = self.store.stamp(self.slug)
        if stamp == self._stamp:
            return False
        saved = self.store.load(self.slug)
        if saved is None:
            return False
        self._stamp = stamp
        self.state = self._resumable(self.engine.restored(saved))
        return True

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
    """The composition root: settings, the built engines, and the games currently open."""

    settings: Settings
    _sessions: dict[str, GameService] = field(default_factory=dict, repr=False)
    engines: dict[EngineId, Engine] = field(init=False)

    def __post_init__(self) -> None:
        self.engines = build_engines(self.settings.packs_dir)

    def busy_refusal(self) -> str | None:
        """Evicting a session mid-turn would let the next tab open a rival writer on that save."""
        playing = [slug for slug, session in self._sessions.items() if session.busy]
        return f"A turn is in flight in {playing[0]!r}." if playing else None

    def reload_settings(self) -> None:
        self.settings = load_settings()
        self.engines = build_engines(self.settings.packs_dir)
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
            stages=None if settings.code_mode else build_turn_agents(engine, settings),
            store=store,
            settings=settings,
            media=open_media(settings, target, scenario, character, store),
        )
