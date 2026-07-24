"""The state panel: the whole GameState as JSON, for inspection."""

from nicegui import ui

from ..session import Session


@ui.refreshable
def state_panel(session: Session) -> None:
    ui.code(session.state.model_dump_json(indent=2), language="json").classes("w-full text-xs")
