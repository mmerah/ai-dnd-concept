from pathlib import Path

from aidm.core.engine import Engine
from aidm.core.enginepack import load_engine
from aidm.core.registry import EnginePlugin
from aidm.core.sheet import Sheet

from .actions import StoryPlan
from .advance import check, offered
from .identity import ENGINE_ID
from .resolve import check_plan, resolve_action

ENGINE_DIR = Path(__file__).parent


def build_story_engine() -> Engine[Sheet]:
    return load_engine(
        ENGINE_DIR,
        ENGINE_ID,
        offered=offered,
        check=check,
        plan_type=StoryPlan,
        check_plan=check_plan,
        resolve_action=resolve_action,
    )


PLUGIN = EnginePlugin(
    id=ENGINE_ID,
    build=lambda _config: build_story_engine(),
    badge=("STORY", "deep-purple-6"),
)
