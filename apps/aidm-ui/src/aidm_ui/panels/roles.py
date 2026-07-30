from aidm.domain.base import ROLES
from nicegui import ui

from ..session_model import Session


def role_badges(session: Session) -> None:
    with ui.row().classes("items-center").style("gap: 0.25rem"):
        for role in ROLES:
            colour = "primary" if session.step == role else "grey-7"
            ui.badge(role).props(f"color={colour}")
