from collections.abc import Iterable, Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheet_engine import SheetEngine
from aidm.state.base import EngineId, Entity, EntityId
from aidm.state.facts import Fact
from aidm.state.world import GameState

from .actions import Cairn2eAction, TurnPlan
from .advance import Cairn2eAdvancement
from .create import Cairn2eCreation
from .mechanics import (
    EFFECTS,
    RULES,
    Cairn2eEffect,
    Mechanics,
    Sheet,
    build_mechanics,
    check_items,
    check_load_limits,
    describe_entity,
    rolled_sheet,
)
from .mechanics import apply as apply_mechanics
from .pack import Pack

ENGINE_ID: EngineId = EngineId("cairn2e")


class Cairn2eEngine(SheetEngine[Sheet, Cairn2eAction]):
    id = ENGINE_ID
    badge = ("CAIRN 2E", "green-8")
    engine_dir = Path(__file__).parent
    plan_type = TurnPlan
    sheet_type = Sheet
    mechanics_type = Mechanics
    effects = EFFECTS

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.subsystems = (Cairn2eAdvancement(self.engine_dir),)
        self.creation = Cairn2eCreation(self.packs)

    def check_overlay(self, payloads: Iterable[dict[str, JsonValue]]) -> None:
        """Cairn authors rules for items as well as actors, so the base check's actor-only
        sheet type cannot validate every payload; each one is tried against either shape."""
        for rules in payloads:
            _ = RULES.validate_python(rules)

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        state.set_mechanics(build_mechanics(state, rules))

    def check_mechanics(self, state: GameState) -> None:
        mechanics = state.mechanics_as(Mechanics)
        check_items(state, mechanics)
        check_load_limits(state, mechanics)

    def apply(self, draft: GameState, effect: Cairn2eEffect) -> list[Fact]:
        """Cairn's own: deprivation refusals, item pools, and the load check the base has not."""
        return apply_mechanics(draft, effect)

    def new_sheet(self, draft: GameState, rng: Random) -> Sheet:
        del draft
        return rolled_sheet(rng)

    def describe(self, state: GameState, entity: Entity) -> str:
        return describe_entity(state, state.mechanics_as(Mechanics), entity)


ENGINE = Cairn2eEngine
