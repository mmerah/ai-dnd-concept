from nicegui import ui

from ..domain.models.base import Role
from .panels.chat import chat
from .panels.progress import progress_panel
from .panels.roles import role_badges
from .panels.state import state_panel
from .panels.trace import trace_panel
from .session import current_session


def _refresh() -> None:
    for panel in (
        chat,
        progress_panel,
        role_badges,
        state_panel,
        trace_panel,
    ):
        panel.refresh()


def _on_step(step: Role) -> None:
    current_session().step = step
    role_badges.refresh()


async def submit(box: ui.input) -> None:
    session = current_session()
    prompt = (box.value or "").strip()
    if not prompt or session.busy:
        return
    session.busy = True  # no await above, so concurrent submissions cannot pass the guard
    box.value = ""
    try:
        await session.app.submit(prompt, on_step=_on_step)
    except Exception as exc:  # keep a failed turn from crashing the UI
        ui.notify(f"{type(exc).__name__}: {exc}", type="negative", multi_line=True)
    finally:
        session.busy, session.step = False, None
        _refresh()


def restart() -> None:
    session = current_session()
    if session.busy:
        return
    session.app.restart()
    _refresh()
