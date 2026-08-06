from pathlib import Path

from aidm.engines.loader import EnginePlugin
from aidm.state.base import EngineId

from .actions import StoryPlan
from .advance import check_delta, offered
from .resolve import check_plan, resolve_action

ENGINE_ID: EngineId = EngineId("story")

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("STORY", "deep-purple-6"),
    engine_dir=Path(__file__).parent,
    plan_type=StoryPlan,
    check_plan=check_plan,
    resolve_action=resolve_action,
    offered=offered,
    check_delta=check_delta,
)
