from dataclasses import dataclass
from typing import ClassVar

from aidm.domain.base import EngineId

from .advancement import StoryAdvancement
from .constants import ENGINE_ID
from .director import StoryDirector
from .lifecycle import StoryLifecycle
from .presentation import StoryPresentation
from .rules import StoryRules


@dataclass(frozen=True, slots=True)
class StoryEngine:
    lifecycle: StoryLifecycle
    rules: StoryRules
    director: StoryDirector
    presentation: StoryPresentation
    advancement: StoryAdvancement
    id: ClassVar[EngineId] = ENGINE_ID


def build_story_engine() -> StoryEngine:
    lifecycle = StoryLifecycle()
    rules = StoryRules(lifecycle)
    return StoryEngine(
        lifecycle=lifecycle,
        rules=rules,
        director=StoryDirector(rules),
        presentation=StoryPresentation(),
        advancement=StoryAdvancement(),
    )
