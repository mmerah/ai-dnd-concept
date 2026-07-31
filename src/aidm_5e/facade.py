from aidm.domain.engine import DependencyStamp, EngineStamp, dependency_stamps
from aidm.engine_api.contracts import (
    AdvancementEngine,
    EngineDirector,
    EngineLifecycle,
    EnginePresentation,
    EngineRules,
)

from .advancement import Dnd5eAdvancement
from .constants import DESCRIPTOR, ENGINE_ID, RULES_VERSION, SCHEMA_VERSION
from .director import Dnd5eDirector
from .engine.ruleset import Ruleset
from .lifecycle import Dnd5eLifecycle
from .presentation import Dnd5ePresentation
from .rules import Dnd5eRules


class Dnd5eEngine:
    descriptor = DESCRIPTOR

    def __init__(self, ruleset: Ruleset) -> None:
        dependencies = dependency_stamps(
            [
                DependencyStamp(
                    kind="content-pack",
                    id=stamp.id,
                    version=stamp.version,
                )
                for stamp in ruleset.stamps
            ]
        )
        self._stamp = EngineStamp(
            id=ENGINE_ID,
            rules_version=RULES_VERSION,
            schema_version=SCHEMA_VERSION,
            dependencies=dependencies,
        )
        rules = Dnd5eRules(ruleset)
        self._lifecycle = Dnd5eLifecycle(ruleset)
        self._rules = rules
        self._director = Dnd5eDirector(rules, self._stamp)
        self._presentation = Dnd5ePresentation(ruleset)
        self._advancement = Dnd5eAdvancement(ruleset)

    @property
    def stamp(self) -> EngineStamp:
        return self._stamp

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
