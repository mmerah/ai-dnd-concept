import logging
from pathlib import Path

from nicegui import ui

from aidm.app.launcher import LaunchTarget, as_engine_id
from aidm.app.session import GameSession, Runtime
from aidm.config import load_settings
from aidm.state.base import content_id

from .busy import refuse_if_busy, working
from .create import creation_page
from .home import home_page
from .panels import (
    advancement_panel,
    chat,
    journal_panel,
    page_header,
    role_badges,
    scene_header,
    sheet_panel,
    state_panel,
    trace_panel,
)

LOGGER = logging.getLogger(__name__)


class GameView:
    def __init__(self, session: GameSession) -> None:
        self.session = session
        self.shown_art: tuple[Path | None, bool] = (None, False)
        # Both are built by the page below this view, and the panels reach them through it.
        self.composer: ui.input | None = None
        self.transcript: ui.scroll_area | None = None

    def fill_composer(self, text: str) -> None:
        if self.composer is not None:
            self.composer.value = text

    @ui.refreshable_method
    def scene(self) -> None:
        scene_header(self.session, self.fill_composer)

    @ui.refreshable_method
    def chat(self) -> None:
        chat(self.session)

    @ui.refreshable_method
    def roles(self) -> None:
        role_badges(self.session)

    @ui.refreshable_method
    def sheet(self) -> None:
        sheet_panel(self.session)

    @ui.refreshable_method
    def journal(self) -> None:
        journal_panel(self.session)

    @ui.refreshable_method
    def trace(self) -> None:
        trace_panel(self.session)

    @ui.refreshable_method
    def advancement(self) -> None:
        advancement_panel(self.session, self.refresh_all)

    @ui.refreshable_method
    def state(self) -> None:
        state_panel(self.session)

    def refresh_all(self) -> None:
        for panel in (
            self.scene,
            self.chat,
            self.roles,
            self.sheet,
            self.journal,
            self.trace,
            self.advancement,
            self.state,
        ):
            panel.refresh()


def on_step(view: GameView, step: str) -> None:
    view.session.step = step
    view.roles.refresh()


def poll_art(view: GameView) -> None:
    """The illustration is generated after the turn commits, so the page watches for it to land."""
    shown = (view.session.scene_art(), view.session.scene_pending())
    if shown != view.shown_art:
        view.shown_art = shown
        view.scene.refresh()


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
            ui.notify("Something is on offer. Check the advancement tab.")
    session.step = None
    view.refresh_all()
    if (transcript := view.transcript) is not None:
        # Deferred: the refreshed bubbles must reach the client before it can scroll past them.
        ui.timer(0.1, lambda: transcript.scroll_to(percent=1.0), once=True)


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

    # The header eats 4rem and the page its own padding, so a bare `h-screen` puts the input
    # row below the fold.
    with ui.splitter(value=55).classes("w-full").style("height: calc(100vh - 6rem)") as splitter:
        with splitter.before, ui.column().classes("w-full h-full p-4").style("gap: 0.5rem"):
            view.scene()
            with ui.scroll_area().classes("w-full flex-grow") as transcript:
                view.chat()
            with ui.row().classes("w-full no-wrap").style("gap: 0.5rem"):
                box = (
                    ui.input(placeholder="What do you do?")
                    .classes("flex-grow")
                    .props("outlined autogrow type=textarea")
                )
                box.on("keydown.enter", lambda: submit(view, box))
                ui.button(icon="send", on_click=lambda: submit(view, box)).props("round")
            view.composer, view.transcript = box, transcript
        with splitter.after, ui.column().classes("w-full h-full").style("gap: 0"):
            advancement = session.engine.advancement
            with ui.tabs().classes("w-full") as tabs:
                scene_tab = ui.tab("scene")
                journal_tab = ui.tab("journal")
                advancement_tab = None if advancement is None else ui.tab(advancement.id)
                dev_tab = ui.tab("dev")
            with ui.tab_panels(tabs, value=scene_tab).classes("w-full flex-grow"):
                with ui.tab_panel(scene_tab), ui.scroll_area().classes("w-full h-full"):
                    view.sheet()
                with ui.tab_panel(journal_tab), ui.scroll_area().classes("w-full h-full"):
                    view.journal()
                if advancement_tab is not None:
                    with ui.tab_panel(advancement_tab), ui.scroll_area().classes("w-full h-full"):
                        view.advancement()
                with ui.tab_panel(dev_tab), ui.scroll_area().classes("w-full h-full"):
                    with ui.expansion("trace", value=True).classes("w-full"):
                        view.trace()
                    with ui.expansion("state").classes("w-full"):
                        view.state()

    if session.media is not None:
        ui.timer(3.0, lambda: poll_art(view))
