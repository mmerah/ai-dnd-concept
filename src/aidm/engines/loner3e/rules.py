from collections.abc import Mapping
from pathlib import Path
from random import Random

from pydantic import JsonValue

from aidm.engines.counters import read_mechanics, write_mechanics
from aidm.engines.loader import Engine, EntityRenderer
from aidm.engines.packs import pack_paths
from aidm.state.base import PLAYER_ID, Counter, EngineId, Entity, EntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_all, apply_branch, check_action, check_effects
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import EFFECTS, Mechanics, Sheet, apply, describe
from .pack import load_packs, twist_table
from .resolve import resolve_question

ENGINE_ID: EngineId = EngineId("loner3e")
LABELS = frozenset[Slug]({"yes-and", "yes", "yes-but", "no-but", "no", "no-and"})
NO_LABELS = frozenset[Slug]()


class Loner3eEngine(Engine):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    plan_type = TurnPlan
    rules_type = Sheet
    engine_dir = Path(__file__).parent

    def __init__(self, extra_packs: Path | None = None) -> None:
        super().__init__(extra_packs)
        self.packs = load_packs(pack_paths(self.engine_dir / "packs", extra_packs))
        self.subsystems = (Loner3eAdvancement(self.engine_dir),)
        self.creation = Loner3eCreation(self.packs)

    def begin(self, state: GameState, rules: Mapping[EntityId, dict[str, JsonValue]]) -> None:
        sheets: dict[EntityId, Sheet] = {}
        for entity in state.world.entities.values():
            authored = rules.get(entity.id)
            if entity.kind != "actor":
                if authored:
                    raise ValueError(f"loner3e writes mechanics for actors only, not {entity.id!r}")
                continue
            sheets[entity.id] = Sheet.model_validate(authored or {})
        write_mechanics(state, Mechanics(sheets=sheets))

    def validate(self, state: GameState) -> None:
        mechanics = read_mechanics(state, Mechanics)
        if PLAYER_ID not in mechanics.sheets:
            raise ValueError("the loner3e mechanics name no player")
        if (chosen := mechanics.sheets[PLAYER_ID].pack) not in self.packs:
            raise ValueError(f"this game plays the {chosen!r} table set, which is not installed")
        actors = {entity.id for entity in state.world.of_kind("actor")}
        if missing := sorted(actors - set(mechanics.sheets)):
            raise ValueError(f"actors carry no character sheet: {missing}")
        if gone := sorted(set(mechanics.sheets) - state.world.all_ids()):
            raise ValueError(f"mechanics name actors the world does not hold: {gone}")

    def seed(self, draft: GameState, entity: Entity, rng: Random) -> None:
        del rng  # nothing on a loner3e sheet is rolled
        mechanics = read_mechanics(draft, Mechanics)
        if entity.kind != "actor" or entity.id in mechanics.sheets:
            return
        # A newcomer starts level with the party: milestones earned before they joined are not owed.
        earned = sum(1 for thread in draft.world.threads.values() if thread.status == "resolved")
        mechanics.sheets[entity.id] = Sheet(milestones=Counter(current=earned))
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
            state,
            plan,
            LABELS,
            apply,
            lambda draft, rng: resolve_question(draft, action, rng, self._twists(state)),
        )

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        facts: list[Fact] = []
        if plan.action is not None:
            settled, outcome = resolve_question(draft, plan.action, rng, self._twists(draft))
            facts = settled + apply_branch(draft, plan, outcome, apply)
        return facts + apply_all(draft, plan.effects, apply)

    def _twists(self, state: GameState) -> tuple[tuple[str, str], ...]:
        """The player's own table set: an NPC sheet is seeded with the default and never selects."""
        return twist_table(self.packs, read_mechanics(state, Mechanics).sheets[PLAYER_ID].pack)


ENGINE = Loner3eEngine
