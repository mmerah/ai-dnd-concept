"""Page layout and the two actions a player can take: submit a prompt, restart the game."""

from nicegui import ui

from . import panels
from .controller import restart, submit
from .session import current_session


def start() -> None:
    current_session()  # build once here so a bad save fails loudly at startup, not per page load
    ui.run(  # pyright: ignore[reportUnknownMemberType] — NiceGUI's signature is untyped
        title="AI Dungeon Master", reload=False, show=False
    )


@ui.page("/")
def page() -> None:
    session = current_session()
    with ui.header().classes("items-center gap-4"):
        ui.label(session.state.scenario.title).classes("text-lg font-bold")
        with ui.row().classes("gap-1 items-center"):
            panels.role_badges(session)
        ui.space()
        ui.button("restart", on_click=restart).props("flat color=white dense")

    with ui.splitter(value=55).classes("w-full h-screen") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4 gap-2"):
            with ui.scroll_area().classes("w-full flex-grow"):
                panels.chat(session)
            with ui.row().classes("w-full no-wrap"):
                box = ui.input(placeholder="What do you do?").classes("flex-grow").props("outlined")
                box.on("keydown.enter", lambda: submit(box))
                ui.button(icon="send", on_click=lambda: submit(box)).props("round")
        with splitter.after, ui.column().classes("w-full h-full gap-0"):
            with ui.tabs().classes("w-full") as tabs:
                trace_tab, state_tab = ui.tab("trace"), ui.tab("state")
            with ui.tab_panels(tabs, value=trace_tab).classes("w-full flex-grow"):
                with ui.tab_panel(trace_tab), ui.scroll_area().classes("w-full h-full"):
                    panels.trace_panel(session)
                with ui.tab_panel(state_tab), ui.scroll_area().classes("w-full h-full"):
                    panels.state_panel(session)
