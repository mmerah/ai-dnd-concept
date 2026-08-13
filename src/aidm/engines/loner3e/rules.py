from collections.abc import Mapping
from pathlib import Path
from random import Random

from aidm.content.authored import Rules
from aidm.engines.counters import read_mechanics, write_mechanics
from aidm.engines.loader import Engine, EntityRenderer
from aidm.state.base import PLAYER_ID, EngineId, EntityId, Slug
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_all, apply_branch, check_action, check_effects
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import Loner3eAdvancement
from .create import Loner3eCreation
from .mechanics import Mechanics, Sheet, apply, describe
from .pack import load_packs, twist_table
from .resolve import resolve_question

ENGINE_ID: EngineId = EngineId("loner3e")
LABELS = frozenset[Slug]({"yes-and", "yes", "yes-but", "no-but", "no", "no-and"})
NO_LABELS = frozenset[Slug]()


class Loner3eEngine(Engine):
    id = ENGINE_ID
    badge = ("LONER 3E", "teal-7")
    plan_type = TurnPlan
    engine_dir = Path(__file__).parent

    def __init__(self) -> None:
        super().__init__()
        packs = load_packs(self.engine_dir / "packs")
        self.twists = twist_table(packs)
        self.advancement = Loner3eAdvancement(self.engine_dir)
        self.creation = Loner3eCreation(packs)

    def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None:
        sheets: dict[EntityId, Sheet] = {}
        for entity in state.world.entities.values():
            authored = rules.get(entity.id)
            if entity.kind != "actor":
                if authored:
                    raise ValueError(f"loner3e writes mechanics for actors only, not {entity.id!r}")
                continue
            sheets[entity.id] = Sheet.model_validate(authored or {})
        write_mechanics(state, Mechanics(sheets=sheets))

    def commit(self, state: GameState) -> None:
        """An actor who joined the world mid-turn is given their numbers by the commit that admits
        them; a payload missing the player is corruption, not a gap to fill."""
        mechanics = read_mechanics(state, Mechanics)
        if PLAYER_ID not in mechanics.sheets:
            raise ValueError("the loner3e mechanics name no player")
        for entity in state.world.of_kind("actor"):
            _ = mechanics.sheets.setdefault(entity.id, Sheet())
        if gone := sorted(set(mechanics.sheets) - state.world.all_ids()):
            raise ValueError(f"mechanics name actors the world does not hold: {gone}")
        write_mechanics(state, mechanics)

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
            lambda draft, rng: resolve_question(draft, action, rng, self.twists),
        )

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        facts: list[Fact] = []
        if plan.action is not None:
            settled, outcome = resolve_question(draft, plan.action, rng, self.twists)
            facts = settled + apply_branch(draft, plan, outcome, apply)
        return facts + apply_all(draft, plan.effects, apply)


ENGINE = Loner3eEngine
