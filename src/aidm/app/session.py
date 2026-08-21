import logging
from asyncio import Task, create_task
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from pydantic_ai import Agent

from aidm.app.authoring.extend import apply_patch, author_extension
from aidm.config import Settings
from aidm.content.authored import Character, Scenario
from aidm.content.store import FileStore, SavedGame, load_character, load_scenario
from aidm.engines.advancement import Advancement, Offer, ProposalBase
from aidm.engines.engine import Engine
from aidm.engines.transact import transact
from aidm.state.model import (
    PLAYER_ID,
    Applied,
    EngineId,
    EntityId,
    Extended,
    Fact,
    Game,
    TraceEntry,
    Turn,
    frontier,
)
from aidm.turn.agents import AdvancementContext, TurnAgents, advisor_agent, build_turn_agents
from aidm.turn.pipeline import TURN_STEPS, run_turn
from aidm.turn.prompts import render_proposal

from .launcher import LaunchTarget
from .media import ICON_DIR, STYLE, Illustrator
from .registry import begin_game, build_engine
from .views import journal_markdown

LOGGER = logging.getLogger(__name__)

# The step name the page lights while an authoring run grows the world.
WORLDSMITH = "worldsmith"


@dataclass(frozen=True, slots=True)
class Drafted:
    """The advancement tab's pending change: what was offered, and what the advisor wrote against
    it."""

    offer: Offer
    proposal: ProposalBase


def build_advisor(
    engine: Engine, settings: Settings
) -> Agent[AdvancementContext, ProposalBase] | None:
    if engine.advancement is None:
        return None
    return advisor_agent(engine.advancement, settings)


def open_media(
    config: Settings,
    target: LaunchTarget,
    scenario: Scenario,
    character: Character,
    store: FileStore,
) -> Illustrator | None:
    """Icons for authored canon are shared by every save of the scenario, the character's own by
    every game it plays; scene art and the icons of what play invented belong to the one save."""
    if not config.media.enabled:
        return None
    scenario_icons = config.scenarios_dir / target.scenario_id / ICON_DIR
    character_icons = config.characters_dir / target.character_id / ICON_DIR
    return Illustrator(
        config=config.media,
        provider=config.providers.for_name(config.media.provider),
        saves=store.media_dir(target.slug),
        icon_dirs={
            **{entity_id: scenario_icons for entity_id in scenario.world.all_ids()},
            **{
                entity_id: character_icons
                for entity_id in (PLAYER_ID, *(item.id for item in character.profile.items))
            },
        },
        style=scenario.art_style or STYLE,
    )


@dataclass
class GameSession:
    target: LaunchTarget
    scenario: Scenario
    character: Character
    engine: Engine
    stages: TurnAgents
    advisor: Agent[AdvancementContext, ProposalBase] | None
    store: FileStore
    settings: Settings
    media: Illustrator | None = None
    rng: Random = field(default_factory=Random)
    entries: list[TraceEntry] = field(default_factory=list)
    busy: bool = False
    step: str | None = None
    drafted: Drafted | None = None
    _illustrations: set[Task[None]] = field(default_factory=set, repr=False)
    state: Game = field(init=False)

    def __post_init__(self) -> None:
        if self.engine.id != self.target.engine:
            raise ValueError(f"{self.target} was opened with the {self.engine.id!r} engine")
        shell = self.store.shell(self.slug)
        if shell is not None and shell.engine != self.engine.id:
            raise ValueError(f"save {self.slug!r} plays {shell.engine!r}, not {self.engine.id!r}")
        saved = None if shell is None else self.store.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(self.engine.restored(saved))

    @property
    def slug(self) -> str:
        return self.target.slug

    @property
    def role_names(self) -> tuple[str, ...]:
        return (*TURN_STEPS, WORLDSMITH) if self.scenario.grows else TURN_STEPS

    async def submit(
        self,
        prompt: str,
        on_step: Callable[[str], None] | None = None,
    ) -> Turn:
        """Commit only after the full turn succeeds."""
        result = await run_turn(
            self.state,
            prompt,
            engine=self.engine,
            stages=self.stages,
            settings=self.settings,
            rng=self.rng,
            on_step=on_step,
        )
        self._commit(result.state, result.turn)
        self._illustrate(result.turn.narration)
        if self.scenario.grows and frontier(self.state.world) <= 1:
            if on_step is not None:
                on_step(WORLDSMITH)
            await self._extend()
        return result.turn

    def scene_art(self) -> Path | None:
        return None if self.media is None else self.media.scene_art(self.state)

    def scene_pending(self) -> bool:
        return self.media is not None and self.media.scene_pending(self.state)

    def illustrate_scene(self) -> None:
        """Draw where the player stands with no turn behind it, so an opening scene has art."""
        self._illustrate("")

    def icon(self, entity_id: EntityId) -> Path | None:
        return None if self.media is None else self.media.icon(entity_id)

    def export_journal(self) -> Path:
        return self.store.write_journal(self.slug, journal_markdown(self.state))

    def _illustrate(self, narration: str) -> None:
        """Fire and forget: the turn is committed already, and the image lands when it lands. The
        set holds the task, which asyncio otherwise garbage-collects mid-flight."""
        if self.media is None:
            return
        task = create_task(self.media.illustrate(self.state, narration))
        self._illustrations.add(task)
        task.add_done_callback(self._illustrations.discard)

    def offers(self) -> tuple[Offer, ...]:
        advancement = self.engine.advancement
        return () if advancement is None else advancement.offers(self.state)

    def pending(self) -> bool:
        """Whether anything is on offer at all, for the notification a finished turn raises."""
        return bool(self.offers())

    async def propose(self, offer: Offer, intent: str) -> ProposalBase:
        """The advisor drafts the change; nothing is committed until the player confirms it."""
        advancement, advisor = self._advancement(), self._advisor()
        deps = AdvancementContext(advancement=advancement, state=self.state, offer=offer)
        prompt = render_proposal(self.engine, self.state, offer, intent)
        return (await advisor.run(prompt, deps=deps)).output

    def preview(self, drafted: Drafted) -> tuple[Fact, ...]:
        """What the change would write, read off a throwaway draft, not the committed state."""
        advancement = self._advancement()
        _, facts = transact(
            self.engine,
            self.state.draft(),
            lambda draft, rng: tuple(
                advancement.resolve(draft, drafted.offer, drafted.proposal, rng)
            ),
            Random(0),
        )
        return facts

    def apply_proposal(self, drafted: Drafted) -> tuple[Fact, ...]:
        """The legality rule runs again here: a turn since the draft may have made it illegal."""
        advancement = self._advancement()
        offer, proposal = drafted.offer, drafted.proposal
        if offer not in advancement.offers(self.state):
            raise ValueError("that change is no longer on offer")
        if refused := advancement.violation(self.state, offer, proposal):
            raise ValueError(refused)
        state, facts = transact(
            self.engine,
            self.state.draft(),
            lambda draft, rng: tuple(advancement.resolve(draft, offer, proposal, rng)),
            self.rng,
        )
        self._commit(state, Applied(subject_id=offer.subject_id, facts=facts))
        return facts

    def _advancement(self) -> Advancement:
        if self.engine.advancement is None:
            raise ValueError(f"the {self.engine.id!r} engine has no advancement")
        return self.engine.advancement

    def _advisor(self) -> Agent[AdvancementContext, ProposalBase]:
        if self.advisor is None:
            raise ValueError(f"the {self.engine.id!r} engine has no advancement")
        return self.advisor

    def restart(self) -> None:
        opening = self._begun()
        self.store.discard(self.slug)
        self.state = opening
        self.entries = []
        self.drafted = None
        self.illustrate_scene()

    def _commit(self, state: Game, entry: TraceEntry) -> None:
        self.store.save(self.slug, SavedGame.of(state))
        self.state = state
        self.entries.append(entry)

    async def _extend(self) -> None:
        """The world grows inside the turn that ran it thin; a failed run costs a log line, and
        the next thin turn tries again."""
        try:
            patch = await author_extension(self.settings, self.engine, self.character, self.state)
            state, facts = transact(
                self.engine,
                self.state.draft(),
                lambda draft, _rng: apply_patch(draft, patch),
                self.rng,
            )
            self._commit(state, Extended(facts=facts))
        except Exception:
            LOGGER.exception("extending %r failed", self.slug)

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

    config: Settings
    _engines: dict[EngineId, Engine] = field(default_factory=dict, repr=False)
    _sessions: dict[str, GameSession] = field(default_factory=dict, repr=False)

    def engine(self, engine_id: EngineId) -> Engine:
        """Memoised: every open session shares the one built engine."""
        held = self._engines.get(engine_id)
        if held is None:
            held = build_engine(engine_id, self.config.packs_dir / engine_id)
            self._engines[engine_id] = held
        return held

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
        config = self.config
        engine = self.engine(target.engine)
        scenario = load_scenario(config.scenarios_dir, target.scenario_id)
        character = load_character(
            config.characters_dir, target.character_id, engine.id, engine.check_overlay
        )
        store = FileStore(config.saves_dir)
        return GameSession(
            target=target,
            scenario=scenario,
            character=character,
            engine=engine,
            stages=build_turn_agents(engine, config),
            advisor=build_advisor(engine, config),
            store=store,
            settings=config,
            media=open_media(config, target, scenario, character, store),
        )
