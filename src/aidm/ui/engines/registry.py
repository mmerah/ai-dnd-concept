from collections.abc import Callable
from typing import Protocol

from aidm.application import GameSession
from aidm.engine import Engine
from aidm.engines.dnd5e.engine import Dnd5eEngine
from aidm.engines.story.engine import StoryEngine

from .dnd5e import Dnd5eAdvancementUi
from .story import StoryAdvancementUi


class AdvancementUi(Protocol):
    def render(self, session: GameSession, refresh: Callable[[], None]) -> None: ...


def advancement_ui(engine: Engine) -> AdvancementUi:
    match engine:
        case StoryEngine():
            return StoryAdvancementUi(engine)
        case Dnd5eEngine():
            return Dnd5eAdvancementUi(engine)
        case _:
            raise TypeError(f"no advancement UI for the {engine.id!r} engine")
