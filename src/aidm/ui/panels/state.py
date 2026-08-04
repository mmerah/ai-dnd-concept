from nicegui import ui

from aidm.kernel.application import GameSession


def state_panel(session: GameSession) -> None:
    ui.code(
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
