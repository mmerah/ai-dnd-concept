from collections.abc import Iterable, Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.counters import read_mechanics, write_mechanics
from aidm.engines.loader import Engine, EntityRenderer
from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheets import check_sheets
from aidm.state.base import EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.plan import Resolver, TurnPlanBase, check_branched, resolve_branched
from aidm.state.world import GameState

from .actions import ATTACK_LABELS, SAVE_LABELS, Attack, Save, TurnPlan
from .advance import Cairn2eAdvancement
from .create import Cairn2eCreation
from .mechanics import (
    EFFECTS,
    RULES,
    Mechanics,
    Sheet,
    apply,
    build_mechanics,
    check_items,
    check_load_limits,
    describe,
    rolled_sheet,
)
from .pack import Pack
from .resolve import resolve_attack, resolve_save

ENGINE_ID: EngineId = EngineId("cairn2e")


class Cairn2eEngine(Engine):
    id = ENGINE_ID
    badge = ("CAIRN 2E", "green-8")
    plan_type = TurnPlan
    rules_type = Sheet
    engine_dir = Path(__file__).parent

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.subsystems = (Cairn2eAdvancement(self.engine_dir),)
        self.creation = Cairn2eCreation(self.packs)

    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        """Cairn authors rules for items as well as actors, so the base check's actor-only
        `rules_type` cannot validate every payload; each one is tried against either shape."""
        for rules in payloads:
            _ = RULES.validate_python(rules)

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        write_mechanics(state, build_mechanics(state, rules))

    def validate(self, state: GameState) -> None:
        mechanics = read_mechanics(state, Mechanics)
        check_sheets(state, mechanics.sheets, ENGINE_ID)
        check_items(state, mechanics)
        check_load_limits(state, mechanics)

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        mechanics = read_mechanics(draft, Mechanics)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        mechanics.sheets[entity.id] = rolled_sheet(rng)
        write_mechanics(draft, mechanics)

    def parse_effect(self, effect: JsonValue) -> Frozen:
        return EFFECTS.validate_python(effect)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return apply(draft, EFFECTS.validate_python(effect))

    def renderer(self, state: GameState) -> EntityRenderer:
        mechanics = read_mechanics(state, Mechanics)
        return lambda entity: describe(state, mechanics, entity)

    def _resolver(self, plan: TurnPlan) -> Resolver | None:
        match plan.action:
            case None:
                return None
            case Save() as save:
                return lambda draft, rng: resolve_save(draft, save, rng)
            case Attack() as attack:
                return lambda draft, rng: resolve_attack(draft, attack, rng)

    def _labels(self, plan: TurnPlan) -> frozenset[Slug]:
        match plan.action:
            case None:
                return frozenset()
            case Save():
                return SAVE_LABELS
            case Attack():
                return ATTACK_LABELS

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        assert isinstance(plan, TurnPlan)
        return check_branched(state, plan, self._labels(plan), apply, self._resolver(plan))

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        return resolve_branched(draft, plan, apply, self._resolver(plan), rng)


ENGINE = Cairn2eEngine
