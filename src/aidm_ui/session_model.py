from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from aidm.application.game import GameApplication
from aidm.domain.base import Role


class AdvancementUi(Protocol):
    def render(self, session: Session, refresh: Callable[[], None]) -> None: ...


@dataclass
class Session:
    app: GameApplication
    advancement: AdvancementUi
    busy: bool = False
    step: Role | None = None
