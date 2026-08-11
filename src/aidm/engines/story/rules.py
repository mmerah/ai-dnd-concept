from pathlib import Path
from random import Random

from aidm.engines.loader import Engine, EnginePlugin
from aidm.state.base import EngineId, Slug
from aidm.state.facts import Fact
from aidm.state.plan import (
    TurnPlanBase,
    apply_branch,
    check_plan_base,
    check_plan_with_trial,
)
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import check_delta, offered
from .resolve import resolve_risk

ENGINE_ID: EngineId = EngineId("story")
LABELS = frozenset[Slug]({"strong", "mixed", "setback"})
NO_LABELS = frozenset[Slug]()


def check(engine: Engine, state: GameState, plan: TurnPlanBase) -> str | None:
    assert isinstance(plan, TurnPlan)
    action = plan.action
    if action is None:
        return check_plan_base(state, plan, NO_LABELS, engine.default_rules)
    return check_plan_with_trial(
        state,
        plan,
        LABELS,
        engine.default_rules,
        lambda draft, rng: resolve_risk(engine, draft, action, rng),
    )


def resolve(engine: Engine, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
    assert isinstance(plan, TurnPlan)
    if plan.action is None:
        return []
    facts, outcome = resolve_risk(engine, draft, plan.action, rng)
    return facts + apply_branch(draft, plan, outcome, engine.default_rules)


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("STORY", "deep-purple-6"),
    engine_dir=Path(__file__).parent,
    plan_type=TurnPlan,
    check=check,
    resolve=resolve,
    offered=offered,
    check_delta=check_delta,
)
