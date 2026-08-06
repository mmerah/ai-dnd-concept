from nicegui import ui

from aidm.app.session import GameSession


def role_badges(session: GameSession) -> None:
    with ui.row().classes("items-center").style("gap: 0.25rem"):
        for role in session.role_names:
            colour = "primary" if session.step == role else "grey-7"
            ui.badge(role).props(f"color={colour}")
