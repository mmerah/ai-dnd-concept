from pathlib import Path

from aidm.engines.loader import EnginePlugin
from aidm.state.base import EngineId

from .actions import Dnd5ePlan
from .advance import check_delta, offered
from .resolve import check_plan, resolve_action

ENGINE_ID: EngineId = EngineId("dnd5e")

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("D&D 5E", "red-9"),
    engine_dir=Path(__file__).parent,
    plan_type=Dnd5ePlan,
    check_plan=check_plan,
    resolve_action=resolve_action,
    offered=offered,
    check_delta=check_delta,
)
