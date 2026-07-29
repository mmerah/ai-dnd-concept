from nicegui import ui

from .controller import restart, submit
from .panels.chat import chat
from .panels.progress import progress_panel
from .panels.roles import role_badges
from .panels.state import state_panel
from .panels.trace import trace_panel
from .session import current_session


def start() -> None:
    current_session()  # fail on a bad save at startup
    ui.run(title="AI Dungeon Master", reload=False, show=False)  # pyright: ignore[reportUnknownMemberType]


@ui.page("/")
def page() -> None:
    session = current_session()
    with ui.header().classes("items-center gap-4"):
        ui.label(session.app.state.scenario.title).classes("text-lg font-bold")
        with ui.row().classes("gap-1 items-center"):
            role_badges(session)
        ui.space()
        ui.button("restart", on_click=restart).props("flat color=white dense")

    with ui.splitter(value=55).classes("w-full h-screen") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4 gap-2"):
            with ui.scroll_area().classes("w-full flex-grow"):
                chat(session)
            with ui.row().classes("w-full no-wrap"):
                box = ui.input(placeholder="What do you do?").classes("flex-grow").props("outlined")
                box.on("keydown.enter", lambda: submit(box))
                ui.button(icon="send", on_click=lambda: submit(box)).props("round")
        with splitter.after, ui.column().classes("w-full h-full gap-0"):
            with ui.tabs().classes("w-full") as tabs:
                trace_tab = ui.tab("trace")
                level_tab, state_tab = ui.tab("level up"), ui.tab("state")
            with ui.tab_panels(tabs, value=trace_tab).classes("w-full flex-grow"):
                with ui.tab_panel(trace_tab), ui.scroll_area().classes("w-full h-full"):
                    trace_panel(session)
                with ui.tab_panel(level_tab), ui.scroll_area().classes("w-full h-full"):
                    progress_panel(session)
                with ui.tab_panel(state_tab), ui.scroll_area().classes("w-full h-full"):
                    state_panel(session)
