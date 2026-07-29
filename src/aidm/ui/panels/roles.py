from nicegui import ui

from ...domain.models.base import ROLES
from ..session import Session


@ui.refreshable
def role_badges(session: Session) -> None:
    for role in ROLES:
        colour = "primary" if session.step == role else "grey-7"
        ui.badge(role).props(f"color={colour}")
