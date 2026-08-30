import logging
from asyncio import Task, create_task
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.authoring.run import growth_run
from aidm.config import Settings, load_settings
from aidm.content.io import FileStore, load_character, load_scenario
from aidm.content.model import Character, Scenario
from aidm.engines.core import Engine, PlayerAction, offered, play_action, transact
from aidm.engines.registry import begin_game, build_engines
from aidm.state.entities import EngineId, EntityId, Slug
from aidm.state.facts import Fact, traced
from aidm.state.model import Game
from aidm.state.play import Answer
from aidm.state.scene import VisibleScene
from aidm.state.tools import Play
from aidm.turn.run import TurnAgents, TurnStep, build_turn_agents, run_segment

from .launch import LaunchTarget
from .media import ICON_DIR, Illustrator

LOGGER = logging.getLogger(__name__)


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
class GameSession:
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

    async def submit(
        self,
        player_input: str | Answer,
        on_step: Callable[[TurnStep], None] | None = None,
        on_fact: Callable[[Fact], None] | None = None,
    ) -> None:
        """Commit only after the full segment succeeds."""
        if self.stages is None:
            raise ValueError("code mode plays the turn in the MCP server, not here")
        state = await run_segment(
            self.state,
            player_input,
            engine=self.engine,
            stages=self.stages,
            settings=self.settings,
            rng=self.rng,
            on_step=on_step,
            on_fact=on_fact,
        )
        self.commit(state)
        self._illustrate(state.history[-1].narration)
        if self.growth_due():
            if on_step is not None:
                on_step("scenario_creator")
            await self._extend()

    def offers(self) -> tuple[tuple[PlayerAction, str, dict[str, JsonValue]], ...]:
        return offered(self.engine, self.state)

    def act(self, name: Slug, raw: Mapping[str, JsonValue]) -> tuple[Fact, ...]:
        state, facts = play_action(self.engine, self.state, name, raw, self.rng)
        self.commit(state)
        return facts

    def scene(self) -> VisibleScene:
        return VisibleScene.revealed_from(self.engine.scene(self.state), self.state.world)

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
        task = create_task(self.media.illustrate(self.state, self.scene(), narration))
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

    def growth_due(self) -> bool:
        return self.scenario.grows and self.engine.growth_due(
            self.state, self.settings.authoring.growth_frontier
        )

    async def _extend(self) -> None:
        """A failure only logs: growth is a bonus, and it retries on the next thin turn."""
        try:
            run = growth_run(self.settings, self.engine, self.character, self.state)
            _ = await run.send(run.opening_prompt)
            _ = self.apply_growth(run.play())
        except Exception:
            LOGGER.exception("extending %r failed", self.slug)

    def apply_growth(self, play: Play) -> tuple[Fact, ...]:
        """Applied to the current state, which may have moved since the pass was authored."""
        state, facts = transact(self.engine.validate, self.state.draft(), play, self.rng)
        self.commit(state)
        LOGGER.info("the world grew: %s", traced(facts))
        return facts

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
    _sessions: dict[str, GameSession] = field(default_factory=dict, repr=False)
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

    def session(self, target: LaunchTarget) -> GameSession:
        """Memoised: a page render must not rebuild the game and drop the turn in flight."""
        held = self._sessions.get(target.slug)
        if held is not None:
            if held.target != target:
                raise ValueError(f"open session {target.slug!r} plays {held.target}, not {target}")
            return held
        opened = self._open(target)
        self._sessions[target.slug] = opened
        return opened

    def _open(self, target: LaunchTarget) -> GameSession:
        settings = self.settings
        scenario = load_scenario(settings.scenarios_dir, target.scenario_id)
        engine = self.engines[scenario.engine]
        character = load_character(settings.characters_dir, target.character_id, engine.id)
        store = FileStore(settings.saves_dir)
        return GameSession(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            stages=None if settings.code_mode else build_turn_agents(engine, settings),
            store=store,
            settings=settings,
            media=open_media(settings, target, scenario, character, store),
        )
