from collections.abc import Callable

from nicegui import ui

from aidm.application import GameSession
from aidm.base import AdvancementDecision


def advancement_panel(session: GameSession, refresh: Callable[[], None]) -> None:
    """The engine renders its own advancement; core only guards the submission."""

    def submit(decision: AdvancementDecision) -> bool:
        # Checked at click time: a turn may have started after the panel rendered.
        if session.busy:
            ui.notify("Finish the current turn first.", type="warning")
            return False
        try:
            _ = session.advance(decision)
        except (TypeError, ValueError) as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return False
        return True

    session.engine.advancement_panel(lambda: session.state, submit, refresh)
