from collections.abc import Callable
from dataclasses import dataclass, field
from random import Random

from aidm.config import Settings
from aidm.content.authored import Character, Scenario
from aidm.content.store import FileSaves, FileTraces, load_character, load_scenario
from aidm.engines.loader import Engine, load_engine, plugin_for
from aidm.state.advancement import AdvancementOffer, ProposalBase
from aidm.state.base import PLAYER_ID, SAVE_VERSION, EngineId, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.turn import Advance, TraceEntry, Turn
from aidm.state.world import GameState, WorldState
from aidm.turn.advancement import AdvisorContext, advisor, render_proposal
from aidm.turn.pipeline import TURN_STEPS, Stages, TurnOptions, build_stages, run_turn
from aidm.turn.roles import Stage

from .launcher import LaunchTarget


def build_engine(engine_id: EngineId, config: Settings) -> Engine:
    """The composition root reads the engine's section; the loader only takes paths."""
    return load_engine(plugin_for(engine_id), config.engine(engine_id).pack_paths)


def begin_game(engine: Engine, scenario: Scenario, character: Character) -> GameState:
    """One opening state, so the app, the evals, and the tests all start a game the same way."""
    world = scenario.world
    player = Entity(
        id=PLAYER_ID,
        kind="actor",
        name=character.name,
        brief=character.brief,
        known=True,
        parent_id=world.starting_location_id,
        traits=list(character.profile.traits),
    )
    entities: dict[EntityId, Entity] = {}
    for entity in (*world.entities, *character.profile.items, player):
        if entity.id in entities:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        # Loaded content outlives the mutable game state, which restart() rebuilds from it.
        entities[entity.id] = entity.model_copy(deep=True)
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
        world=WorldState(
            entities=entities,
            relations={relation.id: relation.model_copy(deep=True) for relation in world.relations},
        ),
        threads={thread.id: thread.model_copy(deep=True) for thread in world.threads},
        hooks=world.hooks,
    )
    engine.begin(state, rules)
    return state


@dataclass
class GameSession:
    target: LaunchTarget
    scenario: Scenario
    character: Character
    engine: Engine
    stages: Stages
    advisor: Stage[AdvisorContext, ProposalBase]
    saves: FileSaves
    traces: FileTraces
    options: TurnOptions
    rng: Random = field(default_factory=Random)
    entries: list[TraceEntry] = field(default_factory=list)
    busy: bool = False
    step: str | None = None
    drafted: ProposalBase | None = None
    state: GameState = field(init=False)

    def __post_init__(self) -> None:
        if self.engine.id != self.target.engine:
            raise ValueError(f"{self.target} was opened with the {self.engine.id!r} engine")
        shell = self.saves.shell(self.slug)
        if shell is not None and shell.engine != self.engine.id:
            raise ValueError(f"save {self.slug!r} plays {shell.engine!r}, not {self.engine.id!r}")
        saved = None if shell is None else self.saves.load(self.slug)
        if saved is None:
            self.state = self._begun()
            return
        self.state = self._resumable(saved)
        self.entries = list(self.traces.load(self.slug))

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
            options=self.options,
            rng=self.rng,
            on_step=on_step,
        )
        self._commit(result.state, result.turn)
        return result.turn

    def offer(self) -> AdvancementOffer | None:
        return self.engine.offered(self.state)

    async def propose(self, intent: str) -> ProposalBase:
        """The advisor drafts the change; nothing is committed until the player confirms it."""
        offer = self._offered()
        deps = AdvisorContext(engine=self.engine, state=self.state, offer=offer)
        return await self.advisor.run(render_proposal(self.engine, self.state, offer, intent), deps)

    def preview(self, proposal: ProposalBase) -> tuple[Fact, ...]:
        """What the change would write, read off a throwaway draft, not the committed state."""
        return self.engine.advance(self.state.draft(), proposal)

    def apply_proposal(self, proposal: ProposalBase) -> tuple[Fact, ...]:
        offer = self._offered()
        refused = self.engine.violation(self.state, offer, proposal)
        if refused is not None:
            raise ValueError(refused)
        draft = self.state.draft()
        facts = self.engine.advance(draft, proposal)
        self.engine.commit(draft)
        self._commit(draft.committed(), Advance(facts=facts))
        return facts

    def _offered(self) -> AdvancementOffer:
        offer = self.offer()
        if offer is None:
            raise ValueError("no advancement is on offer")
        return offer

    def restart(self) -> None:
        opening = self._begun()
        self.saves.discard(self.slug)
        self.traces.discard(self.slug)
        self.state = opening
        self.entries = []
        self.drafted = None

    def _commit(self, state: GameState, entry: TraceEntry) -> None:
        self.saves.save(self.slug, state)
        self.traces.append(self.slug, entry)
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
        """Memoised: building the 5e engine compiles the whole content pack."""
        held = self._engines.get(engine_id)
        if held is None:
            held = build_engine(engine_id, self.config)
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
        options = TurnOptions(
            history_window=config.history_window,
            max_growth=config.max_growth,
        )
        return GameSession(
            target=target,
            scenario=load_scenario(config.scenarios_dir, target.scenario_id, target.engine),
            character=load_character(config.characters_dir, target.character_id, target.engine),
            engine=engine,
            stages=build_stages(engine, config),
            advisor=advisor(engine, config),
            saves=FileSaves(config.saves_dir),
            traces=FileTraces(config.saves_dir),
            options=options,
        )
