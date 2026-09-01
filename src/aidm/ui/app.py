import logging
from contextlib import AsyncExitStack
from functools import partial

from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

from aidm.app.launch import (
    LauncherCatalog,
    LaunchTarget,
    SaveOption,
    launch_target,
    load_catalog,
)
from aidm.app.mcp import MOUNT_PATH, endpoint
from aidm.app.runtime import Runtime
from aidm.app.spawn import CliSpawner
from aidm.config import load_settings
from aidm.core.entities import Slug, content_id

from .create import character_page, scenario_page
from .game import game_page
from .settings import settings_page
from .widgets import page_header

LOGGER = logging.getLogger(__name__)


def home_page(runtime: Runtime) -> None:
    catalog = load_catalog(runtime.settings, runtime.engines)
    with page_header("AI Dungeon Master", home=False):
        ui.button("Settings", icon="settings", on_click=lambda: ui.navigate.to("/settings")).props(
            "flat color=white"
        )
        ui.space()
        ui.label("Choose your game").classes("text-sm opacity-80")

    with ui.column().classes("w-full q-pa-lg items-center").style("gap: 1.5rem"):
        with ui.column().style("width: min(64rem, 100%); gap: 1.5rem"):
            ui.label("Begin an adventure").classes("text-h4 font-bold")
            ui.label("Choose a scenario, then a character written for its rules.").classes(
                "text-body1 opacity-70"
            )
            _new_game(catalog)
            _new_content()
            _saved_games(catalog)


def start() -> None:
    # Without a handler the root logger drops every INFO record, spawns included.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    _register_pages(Runtime(settings, CliSpawner(settings)))
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master",
        port=settings.server_port,
        reload=False,
        show=False,
    )


def _new_game(catalog: LauncherCatalog) -> None:
    with ui.card().classes("w-full q-pa-lg"):
        ui.label("New or current game").classes("text-h6 font-bold")
        if not catalog.scenarios:
            ui.label("No playable scenario was found.").classes("text-negative")
            return
        scenario_id = catalog.scenarios[0].id
        character_id: Slug | None = None

        def choose_scenario(event: ValueChangeEventArguments[str]) -> None:
            nonlocal scenario_id
            scenario_id = content_id(event.value)
            form.refresh()

        def choose_character(event: ValueChangeEventArguments[str]) -> None:
            nonlocal character_id
            character_id = content_id(event.value)
            form.refresh()

        @ui.refreshable
        def form() -> None:
            scenario = catalog.scenario(scenario_id)
            ui.select(
                options={entry.id: entry.title for entry in catalog.scenarios},
                value=scenario_id,
                label="Scenario",
                on_change=choose_scenario,
            ).classes("w-full")
            ui.label(scenario.subtitle).classes("text-sm opacity-70")
            written = {
                entry.id: f"{entry.title} — {entry.subtitle}"
                for entry in catalog.characters_for(scenario.engine)
            }
            chosen = character_id if character_id in written else next(iter(written), None)
            ui.select(
                options=written,
                value=chosen,
                label="Character",
                on_change=choose_character,
            ).classes("w-full")
            if chosen is None:
                ui.label("No character is written for these rules.").classes("text-negative")
                return
            target = launch_target(catalog, scenario_id, chosen)
            started = any(save.target.slug == target.slug for save in catalog.saves)
            ui.button(
                "Continue game" if started else "Start game",
                icon="play_arrow",
                on_click=partial(_open_game, target),
            ).props("color=primary").classes("q-mt-md")

        form()


def _new_content() -> None:
    with ui.row().classes("items-center").style("gap: 0.5rem"):
        ui.button(
            "New character", icon="person_add", on_click=lambda: ui.navigate.to("/create")
        ).props("outline dense")
        ui.button(
            "New scenario", icon="auto_stories", on_click=lambda: ui.navigate.to("/scenario")
        ).props("outline dense")


def _saved_games(catalog: LauncherCatalog) -> None:
    ui.label("Saved games").classes("text-h5 font-bold q-mt-md")
    if not catalog.saves:
        ui.label("No saved games yet.").classes("text-body1 opacity-60")
        return
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for saved in catalog.saves:
            _saved_card(saved)


def _saved_card(saved: SaveOption) -> None:
    with ui.card().classes("w-full q-pa-md"):
        with ui.row().classes("w-full items-center").style("gap: 1rem"):
            with ui.column().classes("col").style("gap: 0.25rem"):
                ui.label(saved.scenario_title).classes("text-h6 font-bold")
                ui.label(f"{saved.character_title} · turn {saved.turn}").classes(
                    "text-sm opacity-70"
                )
            ui.button(
                "Resume",
                icon="play_arrow",
                on_click=partial(_open_game, saved.target),
            ).props("color=primary")


def _open_game(target: LaunchTarget) -> None:
    LOGGER.info("launcher opening %r", target.slug)
    ui.navigate.to(target.path)


def _register_pages(runtime: Runtime) -> None:
    asgi, manager = endpoint(runtime)
    app.mount(MOUNT_PATH, asgi)
    # A mounted app's own lifespan never runs, so the manager's task group is opened by hand.
    running = AsyncExitStack()
    app.on_startup(lambda: running.enter_async_context(manager.run()))  # pyright: ignore[reportUnknownMemberType]
    app.on_shutdown(running.aclose)  # pyright: ignore[reportUnknownMemberType]

    def apply_settings() -> str | None:
        refusal = runtime.busy_refusal()
        if refusal is None:
            runtime.reload_settings()
        return refusal

    @ui.page("/")
    def _index() -> None:  # pyright: ignore[reportUnusedFunction]
        home_page(runtime)

    @ui.page("/game/{slug}/{scenario}/{character}")
    def _game(  # pyright: ignore[reportUnusedFunction]
        slug: str,
        scenario: str,
        character: str,
    ) -> None:
        game_page(
            runtime,
            runtime.session(
                LaunchTarget(
                    slug=slug,
                    scenario_id=content_id(scenario),
                    character_id=content_id(character),
                )
            ),
        )

    @ui.page("/create")
    def _create() -> None:  # pyright: ignore[reportUnusedFunction]
        character_page(runtime)

    @ui.page("/scenario")
    def _scenario() -> None:  # pyright: ignore[reportUnusedFunction]
        scenario_page(runtime)

    @ui.page("/settings")
    def _settings() -> None:  # pyright: ignore[reportUnusedFunction]
        settings_page(runtime.settings, apply_settings)
