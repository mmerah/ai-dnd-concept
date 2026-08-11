from collections.abc import Callable
from pathlib import Path

from aidm.engines.loader import ActionSpec, Engine, EnginePlugin
from aidm.state.base import EngineId, Slug
from aidm.state.effects import AdjustCounter, SpendCounter
from aidm.state.plan import TurnPlanBase
from aidm.state.world import GameState

from .actions import Attack, CastSpell, Check, Improvise, Rest, TurnPlan, UseFeature
from .advance import check_delta, offered
from .resolve import (
    resolve_attack,
    resolve_cast_spell,
    resolve_check,
    resolve_improvise,
    resolve_rest,
    resolve_use_feature,
    spell_of,
)

ENGINE_ID: EngineId = EngineId("dnd5e")
CONTESTED = frozenset[Slug]({"success", "failure"})
UNCONTESTED = frozenset[Slug]()
SLOT = "slot-"


def improvise_labels(engine: Engine, action: Improvise) -> frozenset[Slug]:
    return CONTESTED if action.vs is not None else UNCONTESTED


def cast_labels(engine: Engine, action: CastSpell) -> frozenset[Slug]:
    """Contested only when the spell's facts carry an attack or a save; the trial resolve has
    already validated the ref, so a miss here never surfaces."""
    try:
        record = spell_of(engine.content, action.spell)
    except ValueError:
        return UNCONTESTED
    contested = "attack-type" in record.facts or "save-ability" in record.facts
    return CONTESTED if contested else UNCONTESTED


def check_cast(state: GameState, plan: TurnPlanBase, action: CastSpell) -> str | None:
    return _double_spend(plan, lambda counter: counter.startswith(SLOT))


def check_feature(state: GameState, plan: TurnPlanBase, action: UseFeature) -> str | None:
    return _double_spend(plan, lambda counter: counter == action.counter)


def _double_spend(plan: TurnPlanBase, engine_pays: Callable[[str], bool]) -> str | None:
    written = (*plan.effects, *(effect for branch in plan.branches for effect in branch.effects))
    for effect in written:
        if isinstance(effect, (SpendCounter, AdjustCounter)) and engine_pays(effect.counter):
            return (
                f"the engine already spends {effect.counter!r} for this action: "
                "drop that effect and let the engine pay the cost"
            )
    return None


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("D&D 5E", "red-9"),
    engine_dir=Path(__file__).parent,
    plan_type=TurnPlan,
    actions=(
        ActionSpec(model=Attack, labels=CONTESTED, resolve=resolve_attack),
        ActionSpec(
            model=CastSpell, labels=cast_labels, resolve=resolve_cast_spell, check=check_cast
        ),
        ActionSpec(model=Check, labels=CONTESTED, resolve=resolve_check),
        ActionSpec(
            model=UseFeature, labels=UNCONTESTED, resolve=resolve_use_feature, check=check_feature
        ),
        ActionSpec(model=Rest, labels=UNCONTESTED, resolve=resolve_rest),
        ActionSpec(model=Improvise, labels=improvise_labels, resolve=resolve_improvise),
    ),
    offered=offered,
    check_delta=check_delta,
)
