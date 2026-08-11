from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from nicegui import ui

from aidm.app.session import GameSession


def refuse_if_busy(session: GameSession) -> bool:
    if not session.busy:
        return False
    ui.notify("Finish the current turn first.", type="warning")
    return True


@asynccontextmanager
async def working(session: GameSession) -> AsyncGenerator[None]:
    """A failure is shown to the player and swallowed: the session must never stay busy."""
    session.busy = True
    try:
        yield
    except Exception as error:
        ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)
    finally:
        session.busy = False
