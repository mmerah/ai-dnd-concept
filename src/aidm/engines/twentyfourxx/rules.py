from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.counters import read_mechanics, write_mechanics
from aidm.engines.loader import Engine, EntityRenderer
from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheets import actor_sheets, check_sheets, resolved_threads
from aidm.state.base import Counter, EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_all, apply_branch, check_action, check_effects
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import TwentyfourxxAdvancement
from .create import TwentyfourxxCreation
from .mechanics import EFFECTS, Mechanics, Sheet, apply, describe
from .pack import Pack
from .resolve import resolve_attempt

ENGINE_ID: EngineId = EngineId("twentyfourxx")
LABELS = frozenset[Slug]({"disaster", "setback", "success"})
NO_LABELS = frozenset[Slug]()


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
        write_mechanics(state, Mechanics(sheets=sheets))

    def validate(self, state: GameState) -> None:
        mechanics = read_mechanics(state, Mechanics)
        check_sheets(state, mechanics.sheets, ENGINE_ID)

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a fresh 24xx sheet is rolled
        mechanics = read_mechanics(draft, Mechanics)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: jobs done before they joined are not owed.
        earned = resolved_threads(draft.world)
        mechanics.sheets[entity.id] = Sheet(jobs=Counter(current=earned))
        write_mechanics(draft, mechanics)

    def parse_effect(self, effect: JsonValue) -> Frozen:
        return EFFECTS.validate_python(effect)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return apply(draft, EFFECTS.validate_python(effect))

    def renderer(self, state: GameState) -> EntityRenderer:
        mechanics = read_mechanics(state, Mechanics)
        return lambda entity: describe(mechanics, entity)

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        assert isinstance(plan, TurnPlan)
        action = plan.action
        if action is None:
            return check_effects(state, plan, NO_LABELS, apply)
        return check_action(
            state, plan, LABELS, apply, lambda draft, rng: resolve_attempt(draft, action, rng)
        )

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        facts: list[Fact] = []
        if plan.action is not None:
            settled, outcome = resolve_attempt(draft, plan.action, rng)
            facts = settled + apply_branch(draft, plan, outcome, apply)
        return facts + apply_all(draft, plan.effects, apply)


ENGINE = TwentyfourxxEngine
