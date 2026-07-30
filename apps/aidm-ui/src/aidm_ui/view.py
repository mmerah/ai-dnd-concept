from nicegui import ui

from .panels import chat, roles, state, trace
from .session_model import Session


class GameView:
    def __init__(self, session: Session) -> None:
        self.session = session

    @ui.refreshable_method
    def chat(self) -> None:
        chat.chat(self.session)

    @ui.refreshable_method
    def roles(self) -> None:
        roles.role_badges(self.session)

    @ui.refreshable_method
    def trace(self) -> None:
        trace.trace_panel(self.session)

    @ui.refreshable_method
    def advancement(self) -> None:
        self.session.advancement.render(self.session, self.refresh_all)

    @ui.refreshable_method
    def state(self) -> None:
        state.state_panel(self.session)

    def refresh_all(self) -> None:
        self.chat.refresh()
        self.roles.refresh()
        self.trace.refresh()
        self.advancement.refresh()
        self.state.refresh()
