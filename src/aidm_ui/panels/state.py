from nicegui import ui

from ..session_model import Session


def state_panel(session: Session) -> None:
    ui.code(
        session.app.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
