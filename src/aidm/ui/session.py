"""The open game as the page holds it: the application, plus the two flags only a page has.

Single-player by design, so one session per process is enough. Nothing about the game is duplicated
here — `session.app` owns the state, the turns, the rng and persistence; this owns which role is
working and whether a turn is in flight, because both exist only to be drawn."""

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
    """Process-level, not per-client: `@ui.page` bodies run once per connection, so building a
    session there would reset the trace panel on every browser reload. This is the one call into the
    composition root — NiceGUI gives a page body no other way to be handed one."""
    return Session(app=create_application(settings()))
