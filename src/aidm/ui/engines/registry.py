from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from aidm.application import GameSession
from aidm.engine import Engine

PACKAGE = "aidm.ui.engines"
DECLARATION = "ADVANCEMENT_UI"


class AdvancementUi(Protocol):
    def render(self, session: GameSession, refresh: Callable[[], None]) -> None: ...


@dataclass(frozen=True, slots=True)
class AdvancementUiPlugin:
    """Wraps the factory so the by-name lookup can narrow it instead of casting."""

    build: Callable[[Engine], AdvancementUi]


def advancement_ui(engine: Engine) -> AdvancementUi:
    """Convention over configuration: an engine's UI lives at `aidm.ui.engines.<id>`."""
    module = f"{PACKAGE}.{engine.id}"
    try:
        found = import_module(module)
    except ModuleNotFoundError as error:
        raise ValueError(f"engine {engine.id!r} ships no {module}") from error
    declared = getattr(found, DECLARATION, None)
    if not isinstance(declared, AdvancementUiPlugin):
        raise ValueError(f"{module} declares no {DECLARATION}")
    return declared.build(engine)
