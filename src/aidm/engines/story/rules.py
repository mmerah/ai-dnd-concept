from pathlib import Path

from aidm.engines.loader import EnginePlugin
from aidm.state.base import EngineId

from .advance import check_delta, offered

ENGINE_ID: EngineId = EngineId("story")

PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    badge=("STORY", "deep-purple-6"),
    engine_dir=Path(__file__).parent,
    action_doc="The one risk this turn resolves, or null when nothing is uncertain enough to "
    "roll for.",
    offered=offered,
    check_delta=check_delta,
)
