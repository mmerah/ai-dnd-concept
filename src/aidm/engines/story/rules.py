from pathlib import Path

from aidm.engines.loader import ActionSpec, EnginePlugin
from aidm.state.base import EngineId

from .actions import OUTCOMES, Risk
from .advance import check_delta, offered
from .resolve import check_risk, resolve_risk

ENGINE_ID: EngineId = EngineId("story")

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("STORY", "deep-purple-6"),
    engine_dir=Path(__file__).parent,
    actions=(ActionSpec(model=Risk, labels=OUTCOMES, resolve=resolve_risk, check=check_risk),),
    action_doc="The one risk this turn resolves, or null when nothing is uncertain enough to "
    "roll for.",
    offered=offered,
    check_delta=check_delta,
)
