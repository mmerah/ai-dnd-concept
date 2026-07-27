"""The turn-loop orchestration behind the page: submit a prompt, restart, and refresh the panels."""

from nicegui import ui

from .. import store
from ..domain.models import Role
from ..pipeline import run_turn
from . import panels
from .session import current_session


def _refresh() -> None:
    for panel in (
        panels.chat,
        panels.progress_panel,
        panels.role_badges,
        panels.state_panel,
        panels.trace_panel,
    ):
        panel.refresh()


def _on_step(step: Role) -> None:
    current_session().step = step
    panels.role_badges.refresh()


async def submit(box: ui.input) -> None:
    session = current_session()
    prompt = (box.value or "").strip()
    if not prompt or session.busy:
        return
    session.busy = True  # no await since the check above, so this cannot interleave
    box.value = ""
    try:
        turn = await run_turn(
            session.state,
            prompt,
            on_step=_on_step,
            library=store.library(),
            rng=session.rng,
        )
        session.commit(turn)
    except Exception as exc:  # the UI must not crash; the turn is dropped whole, never half-applied
        ui.notify(f"{type(exc).__name__}: {exc}", type="negative", multi_line=True)
    finally:
        session.busy, session.step = False, None
        _refresh()


def restart() -> None:
    session = current_session()
    if session.busy:
        return
    session.restart()
    _refresh()
