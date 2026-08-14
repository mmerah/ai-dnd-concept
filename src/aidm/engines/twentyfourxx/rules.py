from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.loader import Engine, EntityRenderer
from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheets import actor_sheets, check_sheets, resolved_threads
from aidm.state.base import Counter, EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.plan import Resolver, TurnPlanBase, check_branched, resolve_branched
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import TwentyfourxxAdvancement
from .create import TwentyfourxxCreation
from .mechanics import EFFECTS, Mechanics, Sheet, apply, describe
from .pack import Pack
from .resolve import resolve_attempt

ENGINE_ID: EngineId = EngineId("twentyfourxx")
LABELS = frozenset[Slug]({"disaster", "setback", "success"})


class TwentyfourxxEngine(Engine):
    id = ENGINE_ID
    badge = ("24XX", "indigo-7")
    plan_type = TurnPlan
    rules_type = Sheet
    engine_dir = Path(__file__).parent

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.subsystems = (TwentyfourxxAdvancement(self.engine_dir),)
        self.creation = TwentyfourxxCreation(self.packs)

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        sheets = actor_sheets(state, rules, Sheet, ENGINE_ID)
        state.set_mechanics(Mechanics(sheets=sheets))

    def validate(self, state: GameState) -> None:
        mechanics = state.mechanics_as(Mechanics)
        check_sheets(state, mechanics.sheets, ENGINE_ID)

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a fresh 24xx sheet is rolled
        mechanics = draft.mechanics_as(Mechanics)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: jobs done before they joined are not owed.
        earned = resolved_threads(draft.world)
        mechanics.sheets[entity.id] = Sheet(jobs=Counter(current=earned))

    def parse_effect(self, effect: JsonValue) -> Frozen:
        return EFFECTS.validate_python(effect)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return apply(draft, EFFECTS.validate_python(effect))

    def renderer(self, state: GameState) -> EntityRenderer:
        mechanics = state.mechanics_as(Mechanics)
        return lambda entity: describe(mechanics, entity)

    def _resolver(self, plan: TurnPlan) -> Resolver | None:
        action = plan.action
        if action is None:
            return None
        return lambda draft, rng: resolve_attempt(draft, action, rng)

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        assert isinstance(plan, TurnPlan)
        return check_branched(state, plan, LABELS, apply, self._resolver(plan))

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        return resolve_branched(draft, plan, apply, self._resolver(plan), rng)


ENGINE = TwentyfourxxEngine
