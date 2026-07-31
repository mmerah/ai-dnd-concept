from nicegui import ui

from .bootstrap import create_composition
from .components.engine import show_engine_badge
from .config import load_settings
from .controller import restart, submit
from .home import home_page
from .session import SessionRegistry
from .session_model import Session
from .view import GameView


def start() -> None:
    sessions = SessionRegistry(create_composition(load_settings()))
    _register_pages(sessions)
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master",
        reload=False,
        show=False,
    )


def _register_pages(sessions: SessionRegistry) -> None:
    @ui.page("/")
    def _index() -> None:  # pyright: ignore[reportUnusedFunction]
        home_page(sessions.composition.config)

    @ui.page("/game/{slug}/{scenario_name}/{character_name}")
    def _game(  # pyright: ignore[reportUnusedFunction]
        slug: str,
        scenario_name: str,
        character_name: str,
    ) -> None:
        _game_page(sessions.session(slug, scenario_name, character_name))


def _game_page(session: Session) -> None:
    view = GameView(session)
    with ui.header().classes("items-center").style("gap: 1rem"):
        ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props("flat color=white round")
        ui.label(session.app.state.scenario.title).classes("text-lg font-bold")
        show_engine_badge(session.app.engine.id)
        view.roles()
        ui.space()
        ui.button("restart", on_click=lambda: restart(view)).props("flat color=white dense")

    with ui.splitter(value=55).classes("w-full h-screen") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
            with ui.scroll_area().classes("w-full flex-grow"):
                view.chat()
            with ui.row().classes("w-full no-wrap").style("gap: 0.5rem"):
                box = ui.input(placeholder="What do you do?").classes("flex-grow").props("outlined")
                box.on("keydown.enter", lambda: submit(view, box))
                ui.button(icon="send", on_click=lambda: submit(view, box)).props("round")
        with splitter.after, ui.column().classes("w-full h-full").style("gap: 0"):
            with ui.tabs().classes("w-full") as tabs:
                trace_tab = ui.tab("trace")
                advancement_tab = ui.tab("advancement")
                state_tab = ui.tab("state")
            with ui.tab_panels(tabs, value=trace_tab).classes("w-full flex-grow"):
                with ui.tab_panel(trace_tab), ui.scroll_area().classes("w-full h-full"):
                    view.trace()
                with ui.tab_panel(advancement_tab), ui.scroll_area().classes("w-full h-full"):
                    view.advancement()
                with ui.tab_panel(state_tab), ui.scroll_area().classes("w-full h-full"):
                    view.state()
