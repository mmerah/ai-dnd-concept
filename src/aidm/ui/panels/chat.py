from nicegui import ui

from aidm.workflow.session import GameSession


def chat(session: GameSession) -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    for exchange in session.state.history:
        ui.chat_message(exchange.prompt, name="You", sent=True)
        ui.chat_message(exchange.narration, name="DM")
