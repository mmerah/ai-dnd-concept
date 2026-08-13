import logging

from nicegui import ui

from aidm.app.launcher import LaunchTarget, as_engine_id
from aidm.app.session import GameSession, Runtime
from aidm.config import load_settings
from aidm.state.base import Slug, content_id

from .busy import refuse_if_busy, working
from .create import creation_page
from .home import home_page
from .panels import (
    chat,
    page_header,
    role_badges,
    state_panel,
    subsystem_panel,
    trace_panel,
)

LOGGER = logging.getLogger(__name__)


class GameView:
    def __init__(self, session: GameSession) -> None:
        self.session = session

    @ui.refreshable_method
    def chat(self) -> None:
        chat(self.session)

    @ui.refreshable_method
    def roles(self) -> None:
        role_badges(self.session)

    @ui.refreshable_method
    def trace(self) -> None:
        trace_panel(self.session)

    @ui.refreshable_method
    def subsystem(self, capability: Slug) -> None:
        subsystem_panel(self.session, capability, self.refresh_all)

    @ui.refreshable_method
    def state(self) -> None:
        state_panel(self.session)

    def refresh_all(self) -> None:
        for panel in (self.chat, self.roles, self.trace, self.subsystem, self.state):
            panel.refresh()


def on_step(view: GameView, step: str) -> None:
    view.session.step = step
    view.roles.refresh()


async def submit(view: GameView, box: ui.input) -> None:
    session = view.session
    prompt = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(prompt), session.busy)
    if not prompt or refuse_if_busy(session):
        return
    box.value = ""
    async with working(session):
        was_offered = session.pending()
        await session.submit(prompt, on_step=lambda step: on_step(view, step))
        if not was_offered and session.pending():
            ui.notify("Something is on offer. Check the subsystem tabs.")
    session.step = None
    view.refresh_all()


def restart(view: GameView) -> None:
    session = view.session
    if refuse_if_busy(session):
        return
    session.restart()
    view.refresh_all()


def start() -> None:
    _register_pages(Runtime(load_settings()))
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master",
        reload=False,
        show=False,
    )


def _register_pages(runtime: Runtime) -> None:
    @ui.page("/")
    def _index() -> None:  # pyright: ignore[reportUnusedFunction]
        home_page(runtime.config)

    @ui.page("/game/{slug}/{scenario}/{character}/{engine}")
    def _game(  # pyright: ignore[reportUnusedFunction]
        slug: str,
        scenario: str,
        character: str,
        engine: str,
    ) -> None:
        _game_page(
            runtime.session(
                LaunchTarget(
                    slug=slug,
                    scenario_id=content_id(scenario),
                    character_id=content_id(character),
                    engine=as_engine_id(engine),
                )
            )
        )

    @ui.page("/create/{engine}")
    def _create(engine: str) -> None:  # pyright: ignore[reportUnusedFunction]
        creation_page(runtime, as_engine_id(engine))


def _game_page(session: GameSession) -> None:
    view = GameView(session)
    with page_header(session.state.scenario.title, session.engine.badge):
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
            subsystems = session.engine.subsystems
            with ui.tabs().classes("w-full") as tabs:
                trace_tab = ui.tab("trace")
                subsystem_tabs = [ui.tab(system.id) for system in subsystems]
                state_tab = ui.tab("state")
            with ui.tab_panels(tabs, value=trace_tab).classes("w-full flex-grow"):
                with ui.tab_panel(trace_tab), ui.scroll_area().classes("w-full h-full"):
                    view.trace()
                for system, tab in zip(subsystems, subsystem_tabs, strict=True):
                    with ui.tab_panel(tab), ui.scroll_area().classes("w-full h-full"):
                        view.subsystem(system.id)
                with ui.tab_panel(state_tab), ui.scroll_area().classes("w-full h-full"):
                    view.state()
