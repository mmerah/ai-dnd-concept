from dataclasses import dataclass
from functools import cache

from ..application.game import GameApplication
from ..bootstrap import create_application
from ..config import settings
from ..domain.models import Role


@dataclass
class Session:
    app: GameApplication
    busy: bool = False
    step: Role | None = None


@cache
def current_session() -> Session:
    """Cache globally because page bodies rerun on each connection."""
    return Session(app=create_application(settings()))
