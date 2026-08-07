from collections.abc import Callable
from pathlib import Path
from typing import Any

from aidm.engines.loader import Engine, EnginePlugin
from aidm.state.base import EngineId, Slug
from aidm.state.effects import AdjustCounter, SpendCounter
from aidm.state.packs import ContentMiss, Record, parse_ref
from aidm.state.plan import TurnPlanBase
from aidm.state.world import GameState

from .advance import check_delta, offered

ENGINE_ID: EngineId = EngineId("dnd5e")
CONTESTED = frozenset[Slug]({"success", "failure"})
UNCONTESTED = frozenset[Slug]()
SLOT = "slot-"


def improvise_labels(engine: Engine, action: Any) -> frozenset[Slug]:
    return CONTESTED if action.vs is not None else UNCONTESTED


def cast_labels(engine: Engine, action: Any) -> frozenset[Slug]:
    """Contested only when the spell's facts carry an attack or a save; the trial resolve has
    already validated the ref, so a miss here never surfaces."""
    try:
        record = engine.content.get(parse_ref(action.spell), Record)
    except ValueError:
        return UNCONTESTED
    if isinstance(record, ContentMiss):
        return UNCONTESTED
    contested = "attack-type" in record.facts or "save-ability" in record.facts
    return CONTESTED if contested else UNCONTESTED


def check_cast(state: GameState, plan: TurnPlanBase, action: Any) -> str | None:
    return _double_spend(plan, lambda counter: counter.startswith(SLOT))


def check_feature(state: GameState, plan: TurnPlanBase, action: Any) -> str | None:
    named: str = action.counter
    return _double_spend(plan, lambda counter: counter == named)


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
    actions=(),
    action_doc="The one action this turn resolves, or null when nothing needs resolving.",
    offered=offered,
    check_delta=check_delta,
    dynamic_labels={"cast-spell": cast_labels, "improvise": improvise_labels},
    plan_checks={"cast-spell": check_cast, "use-feature": check_feature},
)
