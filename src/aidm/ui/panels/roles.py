from nicegui import ui

from aidm.base import ROLES

from ..session import Session


def role_badges(session: Session) -> None:
    with ui.row().classes("items-center").style("gap: 0.25rem"):
        for role in ROLES:
            colour = "primary" if session.step == role else "grey-7"
            ui.badge(role).props(f"color={colour}")
