from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from aidm.config import Settings
from aidm.content.authored import Character, Scenario
from aidm.content.store import FileStore, load_character, load_scenario
from aidm.engines.loader import Advancement, AdvancementOffer, Engine, ProposalBase, engine_class
from aidm.state.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity
from aidm.state.facts import Fact
from aidm.state.turn import Advance, TraceEntry, Turn
from aidm.state.world import PARTY_MEMBER, GameState, Relation
from aidm.turn.pipeline import TURN_STEPS, run_turn
from aidm.turn.prompts import render_proposal
from aidm.turn.roles import AdvisorContext, Stage, Stages, advisor, build_stages

from .launcher import LaunchTarget


@dataclass(frozen=True, slots=True)
class Advancer:
    """The advancement capability paired with the advisor that drafts against it, built
    together so the pair cannot be half-present."""

    advancement: Advancement
    advisor: Stage[AdvisorContext, ProposalBase]

    @classmethod
    def of(cls, engine: Engine, settings: Settings) -> "Advancer | None":
        capability = engine.advancement
        return None if capability is None else cls(capability, advisor(capability, settings))


def build_engine(engine_id: EngineId) -> Engine:
    return engine_class(engine_id)()


def begin_game(engine: Engine, scenario: Scenario, character: Character) -> GameState:
    """One opening state, so the app, the evals, and the tests all start a game the same way."""
    authored = scenario.world
    # Loaded content outlives the mutable game state, which restart() rebuilds from it.
    world = authored.world.model_copy(deep=True)
    player = Entity(
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        parent_id=authored.starting_location_id,
        traits=list(character.profile.traits),
    )
    for entity in (*(item.model_copy(deep=True) for item in character.profile.items), player):
        if entity.id in world.entities:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        world.entities[entity.id] = entity
    for companion in authored.starting_party:
        travelling = Relation(kind=PARTY_MEMBER, source=companion, target=PLAYER_ID, known=True)
        world.relations[travelling.id] = travelling
    rules = {
        **scenario.overlay.entities,
        **character.overlay.entities,
        PLAYER_ID: character.overlay.character,
    }
    state = GameState(
        save_version=SAVE_VERSION,
        scenario_id=scenario.id,
        character_id=character.id,
        scenario=scenario.meta,
        engine=engine.id,
        world=world,
    )
    engine.begin(state, rules)
    engine.commit(state)  # begin() only writes the mechanics; the commit validates them
    # An instance handed to a model field is not revalidated, so the composed world asks explicitly.
    return state.committed()


@dataclass
class GameSession:
    target: LaunchTarget
    scenario: Scenario
    character: Character
    engine: Engine
    stages: Stages
    advancer: Advancer | None
    store: FileStore
    settings: Settings
    rng: Random = field(default_factory=Random)
    entries: list[TraceEntry] = field(default_factory=list)
    busy: bool = False
    step: str | None = None
    drafted: ProposalBase | None = None
    state: GameState = field(init=False)

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
        self.state = self._resumable(saved)
        self.entries = list(self.store.load_trace(self.slug))

    @property
    def slug(self) -> str:
        return self.target.slug

    @property
    def role_names(self) -> tuple[str, ...]:
        return TURN_STEPS

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
        return result.turn

    def offer(self) -> AdvancementOffer | None:
        return None if self.advancer is None else self.advancer.advancement.offered(self.state)

    async def propose(self, intent: str) -> ProposalBase:
        """The advisor drafts the change; nothing is committed until the player confirms it."""
        advancer = self._advancer()
        offer = self._offered()
        deps = AdvisorContext(advancement=advancer.advancement, state=self.state, offer=offer)
        prompt = render_proposal(self.engine, self.state, offer, intent)
        return await advancer.advisor.run(prompt, deps)

    def preview(self, proposal: ProposalBase) -> tuple[Fact, ...]:
        """What the change would write, read off a throwaway draft, not the committed state."""
        return self._advancer().advancement.advance(self.state.draft(), proposal)

    def apply_proposal(self, proposal: ProposalBase) -> tuple[Fact, ...]:
        """The legality rule runs again here: a turn since the draft may have made it illegal."""
        advancement = self._advancer().advancement
        refused = advancement.violation(self.state, self._offered(), proposal)
        if refused is not None:
            raise ValueError(refused)
        draft = self.state.draft()
        facts = advancement.advance(draft, proposal)
        self.engine.commit(draft)
        self._commit(draft.committed(), Advance(facts=facts))
        return facts

    def _advancer(self) -> Advancer:
        if self.advancer is None:
            raise ValueError("this engine has no advancement")
        return self.advancer

    def _offered(self) -> AdvancementOffer:
        offer = self.offer()
        if offer is None:
            raise ValueError("no advancement is on offer")
        return offer

    def restart(self) -> None:
        opening = self._begun()
        self.store.discard(self.slug)
        self.state = opening
        self.entries = []
        self.drafted = None

    def _commit(self, state: GameState, entry: TraceEntry) -> None:
        self.store.save(self.slug, state)
        self.store.append_trace(self.slug, entry)
        self.state = state
        self.entries.append(entry)

    def _begun(self) -> GameState:
        return begin_game(self.engine, self.scenario, self.character)

    def _resumable(self, state: GameState) -> GameState:
        if (state.scenario_id, state.character_id) != (self.scenario.id, self.character.id):
            raise ValueError(
                f"save is {state.scenario_id!r}/{state.character_id!r}, "
                f"selected is {self.scenario.id!r}/{self.character.id!r}"
            )
        if state.scenario != self.scenario.meta:
            raise ValueError(
                f"save scenario is {state.scenario.title!r}, "
                f"selected scenario is {self.scenario.meta.title!r}"
            )
        self.engine.commit(state)
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
            held = build_engine(engine_id)
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
        return GameSession(
            target=target,
            scenario=load_scenario(config.scenarios_dir, target.scenario_id, target.engine),
            character=load_character(config.characters_dir, target.character_id, target.engine),
            engine=engine,
            stages=build_stages(engine, config),
            advancer=Advancer.of(engine, config),
            store=FileStore(config.saves_dir),
            settings=config,
        )
