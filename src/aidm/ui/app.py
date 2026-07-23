"""Page layout and the two actions a player can take: submit a prompt, restart the game."""

from nicegui import ui

from .. import store
from ..domain.models import Role
from ..pipeline import run_turn
from . import panels
from .session import SCENARIO, SLUG, session


def _refresh() -> None:
    for panel in (panels.chat, panels.role_badges, panels.state_panel, panels.trace_panel):
        panel.refresh()


def _on_step(step: Role) -> None:
    session.step = step
    panels.role_badges.refresh()


async def submit(box: ui.input) -> None:
    prompt = (box.value or "").strip()
    if not prompt or session.busy:
        return
    session.busy = True  # no await since the check above, so this cannot interleave
    box.value = ""
    try:
        turn = await run_turn(session.state, prompt, on_step=_on_step)
        session.state = turn.state
        session.turns.append(turn)
        store.save(SLUG, session.state)
        store.append_trace(SLUG, turn)
    except Exception as exc:  # the UI must not crash; the turn is dropped whole, never half-applied
        ui.notify(f"{type(exc).__name__}: {exc}", type="negative", multi_line=True)
    finally:
        session.busy, session.step = False, None
        _refresh()


def restart() -> None:
    if session.busy:
        return
    store.reset(SLUG)
    session.state, session.turns = store.new_game(SCENARIO), []
    store.save(SLUG, session.state)
    _refresh()


def start() -> None:
    ui.run(  # pyright: ignore[reportUnknownMemberType] — NiceGUI's signature is untyped
        title="AI Dungeon Master", reload=False, show=False
    )


@ui.page("/")
def page() -> None:
    with ui.header().classes("items-center gap-4"):
        ui.label(session.state.scenario.title).classes("text-lg font-bold")
        with ui.row().classes("gap-1 items-center"):
            panels.role_badges()
        ui.space()
        ui.button("restart", on_click=restart).props("flat color=white dense")

    with ui.splitter(value=55).classes("w-full h-screen") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4 gap-2"):
            with ui.scroll_area().classes("w-full flex-grow"):
                panels.chat()
            with ui.row().classes("w-full no-wrap"):
                box = ui.input(placeholder="What do you do?").classes("flex-grow").props("outlined")
                box.on("keydown.enter", lambda: submit(box))
                ui.button(icon="send", on_click=lambda: submit(box)).props("round")
        with splitter.after, ui.column().classes("w-full h-full gap-0"):
            with ui.tabs().classes("w-full") as tabs:
                trace_tab, state_tab = ui.tab("trace"), ui.tab("state")
            with ui.tab_panels(tabs, value=trace_tab).classes("w-full flex-grow"):
                with ui.tab_panel(trace_tab), ui.scroll_area().classes("w-full h-full"):
                    panels.trace_panel()
                with ui.tab_panel(state_tab), ui.scroll_area().classes("w-full h-full"):
                    panels.state_panel()
