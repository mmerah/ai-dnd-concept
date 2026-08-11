from pathlib import Path
from random import Random

from aidm.engines.loader import Engine, EnginePlugin
from aidm.state.base import EngineId, Slug
from aidm.state.facts import Fact
from aidm.state.plan import TurnPlanBase, apply_all, apply_branch, check_action, check_effects
from aidm.state.world import GameState

from .actions import TurnPlan
from .advance import Growth, advance, check_proposal, offered
from .mechanics import apply, begin, commit, render
from .resolve import resolve_risk

ENGINE_ID: EngineId = EngineId("story")
LABELS = frozenset[Slug]({"strong", "mixed", "setback"})
NO_LABELS = frozenset[Slug]()


def check(engine: Engine, state: GameState, plan: TurnPlanBase) -> str | None:
    del engine
    assert isinstance(plan, TurnPlan)
    action = plan.action
    if action is None:
        return check_effects(state, plan, NO_LABELS, apply)
    return check_action(
        state, plan, LABELS, apply, lambda draft, rng: resolve_risk(draft, action, rng)
    )


def resolve(engine: Engine, draft: GameState, plan: TurnPlanBase, rng: Random) -> list[Fact]:
    del engine
    assert isinstance(plan, TurnPlan)
    facts: list[Fact] = []
    if plan.action is not None:
        settled, outcome = resolve_risk(draft, plan.action, rng)
        facts = settled + apply_branch(draft, plan, outcome, apply)
    return facts + apply_all(draft, plan.effects, apply)


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("STORY", "deep-purple-6"),
    engine_dir=Path(__file__).parent,
    plan_type=TurnPlan,
    proposal_type=Growth,
    begin=begin,
    commit=commit,
    render=render,
    check=check,
    resolve=resolve,
    offered=offered,
    advance=advance,
    check_proposal=check_proposal,
)
