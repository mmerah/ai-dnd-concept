from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from aidm.application import GameApplication
from aidm.base import Role
from aidm.engine import Engine


class AdvancementUi(Protocol):
    @property
    def engine(self) -> Engine: ...

    def render(self, session: "Session", refresh: Callable[[], None]) -> None: ...


@dataclass
class Session:
    app: GameApplication
    advancement: AdvancementUi
    busy: bool = False
    step: Role | None = None

    def __post_init__(self) -> None:
        if self.advancement.engine is not self.app.engine:
            raise ValueError("advancement UI and application must share one engine instance")
