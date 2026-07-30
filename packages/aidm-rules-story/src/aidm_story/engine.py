from aidm.domain.engine import EngineStamp
from aidm.engine_api.contracts import (
    AdvancementEngine,
    EngineDirector,
    EngineLifecycle,
    EnginePresentation,
    EngineRules,
)

from .advancement import StoryAdvancement
from .constants import DESCRIPTOR, ENGINE_ID, RULES_VERSION, SCHEMA_VERSION
from .director import StoryDirector
from .lifecycle import StoryLifecycle
from .presentation import StoryPresentation
from .rules import StoryRules


class StoryEngine:
    descriptor = DESCRIPTOR

    def __init__(self) -> None:
        lifecycle = StoryLifecycle()
        self._lifecycle = lifecycle
        self._rules = StoryRules(lifecycle)
        self._director = StoryDirector(self._rules, self.stamp)
        self._presentation = StoryPresentation()
        self._advancement = StoryAdvancement()

    @property
    def stamp(self) -> EngineStamp:
        return EngineStamp(
            id=ENGINE_ID,
            rules_version=RULES_VERSION,
            schema_version=SCHEMA_VERSION,
        )

    @property
    def lifecycle(self) -> EngineLifecycle:
        return self._lifecycle

    @property
    def director(self) -> EngineDirector:
        return self._director

    @property
    def rules(self) -> EngineRules:
        return self._rules

    @property
    def presentation(self) -> EnginePresentation:
        return self._presentation

    @property
    def advancement(self) -> AdvancementEngine:
        return self._advancement


def create_story_engine() -> StoryEngine:
    return StoryEngine()
