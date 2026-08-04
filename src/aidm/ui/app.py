import logging

from nicegui import ui

from aidm.core.base import Role, content_id
from aidm.core.config import load_settings
from aidm.core.registry import as_engine_id
from aidm.workflow.session import GameSession, LaunchTarget, Runtime

from .components.engine import show_engine_badge
from .home import home_page
from .panels import advancement, chat, roles, state, trace

LOGGER = logging.getLogger(__name__)


class GameView:
    def __init__(self, session: GameSession) -> None:
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
        advancement.advancement_panel(self.session, self.refresh_all)

    @ui.refreshable_method
    def state(self) -> None:
        state.state_panel(self.session)

    def refresh_all(self) -> None:
        self.chat.refresh()
        self.roles.refresh()
        self.trace.refresh()
        self.advancement.refresh()
        self.state.refresh()


def on_step(view: GameView, step: Role) -> None:
    view.session.step = step
    view.roles.refresh()


async def submit(view: GameView, box: ui.input) -> None:
    session = view.session
    prompt = (box.value or "").strip()
    LOGGER.info("player submitted prompt: non_empty=%s busy=%s", bool(prompt), session.busy)
    if not prompt:
        return
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
        return
    session.busy = True
    box.value = ""
    try:
        advancement_was_available = session.advancement_available()
        await session.submit(prompt, on_step=lambda step: on_step(view, step))
        if not advancement_was_available and session.advancement_available():
            ui.notify("Advancement unlocked. Open the Advancement tab to choose it.")
    except Exception as error:
        ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)
    finally:
        session.busy = False
        session.step = None
        view.refresh_all()


def restart(view: GameView) -> None:
    session = view.session
    if session.busy:
        ui.notify("Finish the current turn first.", type="warning")
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


def _game_page(session: GameSession) -> None:
    view = GameView(session)
    with ui.header().classes("items-center").style("gap: 1rem"):
        ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props("flat color=white round")
        ui.label(session.state.scenario.title).classes("text-lg font-bold")
        show_engine_badge(session.engine.id)
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
