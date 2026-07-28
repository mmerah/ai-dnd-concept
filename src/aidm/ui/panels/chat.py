"""The chat panel: the player's prompts and the DM's narration, in order."""

from nicegui import ui

from ..session import Session


@ui.refreshable
def chat(session: Session) -> None:
    if not session.app.state.history:
        ui.label(session.app.state.scenario.premise).classes("text-sm italic opacity-70")
    for exchange in session.app.state.history:
        ui.chat_message(exchange.prompt, name="You", sent=True)
        ui.chat_message(exchange.narration, name="DM")
