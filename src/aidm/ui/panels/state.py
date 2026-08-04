from nicegui import ui

from aidm.workflow.session import GameSession


def state_panel(session: GameSession) -> None:
    ui.code(
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
