import logging

from nicegui import ui

from aidm.domain.base import Role

from .view import GameView

LOGGER = logging.getLogger(__name__)


def on_step(view: GameView, step: Role) -> None:
    view.session.step = step
    view.roles.refresh()


async def submit(view: GameView, box: ui.input) -> None:
    session = view.session
    prompt = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(prompt), session.busy)
    if not prompt:
        return
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
        return
    session.busy = True
    box.value = ""
    try:
        advancement_was_available = session.app.advancement_available()
        await session.app.submit(prompt, on_step=lambda step: on_step(view, step))
        if not advancement_was_available and session.app.advancement_available():
            ui.notify("Advancement unlocked. Open the Advancement tab to choose it.")
    except Exception as error:
        ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)
    finally:
        session.busy = False
        session.step = None
        view.refresh_all()


def restart(view: GameView) -> None:
    session = view.session
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
        return
    session.app.restart()
    view.refresh_all()
