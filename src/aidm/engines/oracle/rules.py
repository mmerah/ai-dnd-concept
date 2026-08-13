from collections.abc import Mapping
from pathlib import Path
from random import Random

from aidm.content.authored import Rules
from aidm.engines.loader import Engine, EntityRenderer
from aidm.state.base import EngineId, EntityId, Slug
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_all, apply_branch, check_action, check_effects
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import OracleAdvancement
from .create import OracleCreation
from .mechanics import apply, begin, commit, render
from .resolve import resolve_question

ENGINE_ID: EngineId = EngineId("oracle")
LABELS = frozenset[Slug]({"yes-and", "yes", "yes-but", "no-but", "no", "no-and"})
NO_LABELS = frozenset[Slug]()


class OracleEngine(Engine):
    id = ENGINE_ID
    badge = ("ORACLE", "teal-7")
    plan_type = TurnPlan
    engine_dir = Path(__file__).parent

    def __init__(self) -> None:
        super().__init__()
        self.advancement = OracleAdvancement(self.engine_dir)
        self.creation = OracleCreation()

    def begin(self, state: GameState, rules: Mapping[EntityId, Rules]) -> None:
        begin(state, rules)

    def commit(self, state: GameState) -> None:
        commit(state)

    def renderer(self, state: GameState) -> EntityRenderer:
        return render(state)

    def check_plan(self, state: GameState, plan: TurnPlanBase) -> str | None:
        assert isinstance(plan, TurnPlan)
        action = plan.action
        if action is None:
            return check_effects(state, plan, NO_LABELS, apply)
        return check_action(
            state, plan, LABELS, apply, lambda draft, rng: resolve_question(draft, action, rng)
        )

    def resolve_action(self, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
        assert isinstance(plan, TurnPlan)
        facts: list[Fact] = []
        if plan.action is not None:
            settled, outcome = resolve_question(draft, plan.action, rng)
            facts = settled + apply_branch(draft, plan, outcome, apply)
        return facts + apply_all(draft, plan.effects, apply)


ENGINE = OracleEngine
