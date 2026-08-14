from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.loader import Engine, EntityRenderer
from aidm.engines.packs import load_packs, pack_paths
from aidm.engines.sheets import actor_sheets, check_sheets, resolved_threads
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.plan import Resolver, TurnPlanBase, check_branched, resolve_branched
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import EFFECTS, Mechanics, Sheet, apply, describe
from .pack import Pack, twist_table
from .resolve import resolve_question

ENGINE_ID: EngineId = EngineId("loner3e")
LABELS = frozenset[Slug]({"yes-and", "yes", "yes-but", "no-but", "no", "no-and"})


class Loner3eEngine(Engine):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    plan_type = TurnPlan
    rules_type = Sheet
    engine_dir = Path(__file__).parent

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs), Pack)
        self.subsystems = (Loner3eAdvancement(self.engine_dir),)
        self.creation = Loner3eCreation(self.packs)

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        sheets = actor_sheets(state, rules, Sheet, ENGINE_ID)
        state.set_mechanics(Mechanics(sheets=sheets))

    def validate(self, state: GameState) -> None:
        mechanics = state.mechanics_as(Mechanics)
        check_sheets(state, mechanics.sheets, ENGINE_ID)
        if (chosen := mechanics.sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a loner3e sheet is rolled
        mechanics = draft.mechanics_as(Mechanics)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: milestones earned before they joined are not owed.
        earned = resolved_threads(draft.world)
        mechanics.sheets[entity.id] = Sheet(milestones=Counter(current=earned))

    def parse_effect(self, effect: JsonValue) -> Frozen:
        return EFFECTS.validate_python(effect)

    def apply_effect(self, draft: GameState, effect: JsonValue) -> list[Fact]:
        return apply(draft, EFFECTS.validate_python(effect))

    def renderer(self, state: GameState) -> EntityRenderer:
        mechanics = state.mechanics_as(Mechanics)
        return lambda entity: describe(mechanics, entity)

    def _resolver(self, state: GameState, plan: TurnPlan) -> Resolver | None:
        action = plan.action
        if action is None:
            return None
        twists = self._twists(state)
        return lambda draft, rng: resolve_question(draft, action, rng, twists)

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        assert isinstance(plan, TurnPlan)
        return check_branched(state, plan, LABELS, apply, self._resolver(state, plan))

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        return resolve_branched(draft, plan, apply, self._resolver(draft, plan), rng)

    def _twists(self, state: GameState) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, state.mechanics_as(Mechanics).sheets[PLAYER_ID].pack)


ENGINE = Loner3eEngine
