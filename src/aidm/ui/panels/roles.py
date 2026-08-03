from nicegui import ui

from aidm.application import GameSession
from aidm.base import ROLES


def role_badges(session: GameSession) -> None:
    with ui.row().classes("items-center").style("gap: 0.25rem"):
        for role in ROLES:
            colour = "primary" if session.step == role else "grey-7"
            ui.badge(role).props(f"color={colour}")
