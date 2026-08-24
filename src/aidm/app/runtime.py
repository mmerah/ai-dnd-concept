import logging
from asyncio import Task, create_task
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from pydantic_ai import Agent

from aidm.app.authoring import apply_patch, author_extension
from aidm.config import Settings
from aidm.content.io import FileStore, SavedGame, load_character, load_scenario
from aidm.content.model import Character, Scenario
from aidm.engines.core import Advancement, Engine, Offer, ProposalBase, transact
from aidm.state.entities import PLAYER_ID, EngineId, EntityId, Frozen
from aidm.state.facts import Fact
from aidm.state.model import Game, ThreadStatus, frontier
from aidm.state.play import Answer, Applied, Extended, Line, MechanicEvent, TraceEntry, Turn
from aidm.turn.context import render_proposal
from aidm.turn.run import (
    AdvancementContext,
    TurnAgents,
    TurnStep,
    advisor_agent,
    build_turn_agents,
    run_segment,
)

from .launch import LaunchTarget, begin_game, build_engine
from .media import ICON_DIR, Illustrator


class ThreadSummary(Frozen):
    title: str
    status: ThreadStatus
    stage: str | None = None
    clock: str = ""


def thread_summaries(state: Game) -> tuple[ThreadSummary, ...]:
    return tuple(
        ThreadSummary(
            title=thread.title,
            status=thread.status,
            stage=None if thread.stage is None else thread.stage.replace("-", " "),
            clock=""
            if thread.clock is None
            else f"{thread.clock.current} / {thread.clock.maximum}",
        )
        for thread in sorted(state.world.threads, key=lambda thread: thread.title)
    )


def journal_markdown(state: Game) -> str:
    """A projection only: the journal is written for a reader and never read back."""
    threads = thread_summaries(state)
    lines = [f"# {state.scenario.title}", "", state.scenario.premise, ""]
    for number, exchange in enumerate(state.history, start=1):
        told = "\n".join(attributed_line(state, line) for line in exchange.lines)
        lines.extend((f"## Turn {number}", "", f"> {exchange.prompt}", "", told, ""))
    if threads:
        lines.extend(("## Threads", ""))
        lines.extend(f"- {_thread_line(thread)}" for thread in threads)
        lines.append("")
    return "\n".join(lines)


def attributed_line(state: Game, line: Line) -> str:
    """A speaker is named, because a bare quote reads as narration once the bubbles are gone."""
    speaker = None if line.speaker_id is None else state.world.require(line.speaker_id)
    return line.text if speaker is None else f"**{speaker.name}:** {line.text}"


def _thread_line(thread: ThreadSummary) -> str:
    stage = f" at {thread.stage}" if thread.stage is not None else ""
    clock = f" [{thread.clock}]" if thread.clock else ""
    return f"**{thread.title}** — {thread.status}{stage}{clock}"


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Drafted:
    """Hold an advancement offer and its uncommitted proposal."""

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
    """Share authored icons across games while keeping generated canon and scenes per save."""
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
        style=scenario.art_style or config.media.style,
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
    step: TurnStep | None = None
    drafted: Drafted | None = None
    _illustrations: set[Task[None]] = field(default_factory=set, repr=False)
    state: Game = field(init=False)

    def __post_init__(self) -> None:
        if self.engine.id != self.target.engine:
            raise ValueError(f"{self.target} was opened with the {self.engine.id!r} engine")
        saved = self.store.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        if saved.engine != self.engine.id:
            raise ValueError(f"save {self.slug!r} plays {saved.engine!r}, not {self.engine.id!r}")
        self.state = self._resumable(self.engine.restored(saved))

    @property
    def slug(self) -> str:
        return self.target.slug

    async def submit(
        self,
        player_input: str | Answer,
        on_step: Callable[[TurnStep], None] | None = None,
        on_event: Callable[[MechanicEvent], None] | None = None,
    ) -> Turn:
        """Commit only after the full segment succeeds."""
        result = await run_segment(
            self.state,
            player_input,
            engine=self.engine,
            stages=self.stages,
            settings=self.settings,
            rng=self.rng,
            on_step=on_step,
            on_event=on_event,
        )
        self._commit(result.state, result.turn)
        self._illustrate(result.turn.narration)
        if (
            self.scenario.grows
            and frontier(self.state.world) <= self.settings.authoring.growth_frontier
        ):
            if on_step is not None:
                on_step("worldsmith")
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
        """Retain background tasks because asyncio may collect unreferenced tasks early."""
        if self.media is None:
            return
        task = create_task(self.media.illustrate(self.state, narration))
        self._illustrations.add(task)
        task.add_done_callback(self._illustrations.discard)

    def offers(self) -> tuple[Offer, ...]:
        advancement = self.engine.advancement
        # An advance mid-suspension could invalidate the frozen payload the decision holds.
        if advancement is None or self.state.pending is not None:
            return ()
        return advancement.offers(self.state)

    def advancement_offered(self) -> bool:
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
        if refused := advancement.advance_refusal(self.state, offer, proposal):
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
        self.store.save(self.slug, SavedGame.from_game(state))
        self.state = state
        self.entries.append(entry)

    async def _extend(self) -> None:
        """Log failed growth so the next thin turn can retry it."""
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
