from pathlib import Path

from aidm.engines.loader import ActionSpec, EnginePlugin
from aidm.state.base import EngineId, Slug

from .actions import Risk, TurnPlan
from .advance import check_delta, offered
from .resolve import resolve_risk

ENGINE_ID: EngineId = EngineId("story")
LABELS = frozenset[Slug]({"strong", "mixed", "setback"})

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("STORY", "deep-purple-6"),
    engine_dir=Path(__file__).parent,
    plan_type=TurnPlan,
    actions=(ActionSpec(model=Risk, labels=LABELS, resolve=resolve_risk),),
    offered=offered,
    check_delta=check_delta,
)
