from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from aidm.domain.base import EngineId

from .advancement import Dnd5eAdvancement
from .constants import ENGINE_ID
from .content.library import load
from .director import Dnd5eDirector
from .engine.pack_ruleset import compile_ruleset
from .engine.ruleset import Ruleset
from .lifecycle import Dnd5eLifecycle
from .presentation import Dnd5ePresentation
from .rules import Dnd5eRules

SHIPPED_PACK = Path(__file__).parent / "data" / "srd-2014"


@dataclass(frozen=True, slots=True)
class Dnd5eEngine:
    lifecycle: Dnd5eLifecycle
    rules: Dnd5eRules
    director: Dnd5eDirector
    presentation: Dnd5ePresentation
    advancement: Dnd5eAdvancement
    id: ClassVar[EngineId] = ENGINE_ID


def build_dnd5e_engine(pack_paths: Sequence[Path] | None = None) -> Dnd5eEngine:
    ruleset = compile_ruleset(load((SHIPPED_PACK,) if pack_paths is None else tuple(pack_paths)))
    return dnd5e_engine(ruleset)


def dnd5e_engine(ruleset: Ruleset) -> Dnd5eEngine:
    rules = Dnd5eRules(ruleset)
    return Dnd5eEngine(
        lifecycle=Dnd5eLifecycle(ruleset),
        rules=rules,
        director=Dnd5eDirector(rules),
        presentation=Dnd5ePresentation(ruleset),
        advancement=Dnd5eAdvancement(ruleset),
    )
