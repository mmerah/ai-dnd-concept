from collections.abc import Callable
from pathlib import Path

from aidm.engines.loader import Engine, EnginePlugin
from aidm.state.base import EngineId, Slug
from aidm.state.effects import AdjustCounter, SpendCounter
from aidm.state.plan import TurnPlanBase, check_plan_base, check_plan_with_trial
from aidm.state.world import GameState

from .actions import Action, Attack, CastSpell, Check, Improvise, Rest, TurnPlan, UseFeature
from .advance import check_delta, offered
from .resolve import resolve, resolve_action, spell_of

ENGINE_ID: EngineId = EngineId("dnd5e")
CONTESTED = frozenset[Slug]({"success", "failure"})
UNCONTESTED = frozenset[Slug]()
SLOT = "slot-"


def check(engine: Engine, state: GameState, plan: TurnPlanBase) -> str | None:
    assert isinstance(plan, TurnPlan)
    action = plan.action
    if action is None:
        return check_plan_base(state, plan, UNCONTESTED, engine.default_rules)
    if refusal := _double_spend(plan, action):
        return refusal
    return check_plan_with_trial(
        state,
        plan,
        _labels(engine, action),
        engine.default_rules,
        lambda draft, rng: resolve_action(engine, draft, action, rng),
    )


def _labels(engine: Engine, action: Action) -> frozenset[Slug]:
    """Contested only when the roll can fail: for a spell, when its facts carry an attack or a
    save. A bad ref falls back here; the trial resolve refuses it before the labels are read."""
    match action:
        case Attack() | Check():
            return CONTESTED
        case Improvise():
            return CONTESTED if action.vs is not None else UNCONTESTED
        case CastSpell():
            try:
                record = spell_of(engine.content, action.spell)
            except ValueError:
                return UNCONTESTED
            contested = "attack-type" in record.facts or "save-ability" in record.facts
            return CONTESTED if contested else UNCONTESTED
        case UseFeature() | Rest():
            return UNCONTESTED


def _double_spend(plan: TurnPlanBase, action: Action) -> str | None:
    """The engine pays the action's own cost; a plan that also writes it spends twice."""
    engine_pays = _paid_by_engine(action)
    if engine_pays is None:
        return None
    written = (*plan.effects, *(effect for branch in plan.branches for effect in branch.effects))
    for effect in written:
        if isinstance(effect, (SpendCounter, AdjustCounter)) and engine_pays(effect.counter):
            return (
                f"the engine already spends {effect.counter!r} for this action: "
                "drop that effect and let the engine pay the cost"
            )
    return None


def _paid_by_engine(action: Action) -> Callable[[str], bool] | None:
    match action:
        case CastSpell():
            return lambda counter: counter.startswith(SLOT)
        case UseFeature():
            return lambda counter: counter == action.counter
        case _:
            return None


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("D&D 5E", "red-9"),
    engine_dir=Path(__file__).parent,
    plan_type=TurnPlan,
    check=check,
    resolve=resolve,
    offered=offered,
    check_delta=check_delta,
)
