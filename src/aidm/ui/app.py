import logging
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
from aidm.app.runtime import Runtime
from aidm.config import load_settings
from aidm.harness.claude import ClaudeDriver
from aidm.harness.codex import CodexDriver
from aidm.harness.driver import Driver
from aidm.state.entities import Slug, content_id

from .create import agent_scenario_page, character_page, scenario_page
from .game import game_page
from .settings import settings_page
from .widgets import page_header, show_engine_badge

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
            _new_game(catalog, runtime)
            _new_content(runtime)
            _saved_games(catalog, runtime)


def _new_game(catalog: LauncherCatalog, runtime: Runtime) -> None:
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
            engine = scenario.engines[0]
            show_engine_badge(runtime.engines[engine].badge)
            ui.select(
                options={entry.id: entry.title for entry in catalog.scenarios},
                value=scenario_id,
                label="Scenario",
                on_change=choose_scenario,
            ).classes("w-full")
            ui.label(scenario.subtitle).classes("text-sm opacity-70")
            written = {
                entry.id: f"{entry.title} — {entry.subtitle}"
                for entry in catalog.characters_for(engine)
            }
            # The character last chosen may have no rules under a scenario chosen since.
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


def _new_content(runtime: Runtime) -> None:
    with ui.row().classes("items-center").style("gap: 0.5rem"):
        # Authoring calls a model, and only `external` has neither a key nor an agent to ask.
        if runtime.settings.harness == "external":
            ui.label("New scenario: call begin_scenario() in the terminal.").classes(
                "text-sm opacity-70"
            )
        else:
            ui.button(
                "New scenario",
                icon="auto_stories",
                on_click=lambda: ui.navigate.to("/create-scenario"),
            ).props("outline dense")
        ui.label("New character:").classes("text-sm opacity-70")
        for engine_id in runtime.engines:
            ui.button(
                engine_id,
                icon="person_add",
                on_click=partial(_navigate_create, engine_id),
            ).props("outline dense")


def _navigate_create(engine: str) -> None:
    ui.navigate.to(f"/create/{engine}")


def _saved_games(catalog: LauncherCatalog, runtime: Runtime) -> None:
    ui.label("Saved games").classes("text-h5 font-bold q-mt-md")
    if not catalog.saves:
        ui.label("No saved games yet.").classes("text-body1 opacity-60")
        return
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for saved in catalog.saves:
            _saved_card(saved, runtime)


def _saved_card(saved: SaveOption, runtime: Runtime) -> None:
    with ui.card().classes("w-full q-pa-md"):
        with ui.row().classes("w-full items-center").style("gap: 1rem"):
            with ui.column().classes("col").style("gap: 0.25rem"):
                ui.label(saved.scenario_title).classes("text-h6 font-bold")
                ui.label(f"{saved.character_title} · turn {saved.turn}").classes(
                    "text-sm opacity-70"
                )
            show_engine_badge(runtime.engines[saved.engine].badge)
            ui.button(
                "Resume",
                icon="play_arrow",
                on_click=partial(_open_game, saved.target),
            ).props("color=primary")


def _open_game(target: LaunchTarget) -> None:
    LOGGER.info("launcher opening %r", target.slug)
    ui.navigate.to(target.path)


def start() -> None:
    _register_pages(Runtime(load_settings()))
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master",
        reload=False,
        show=False,
    )


def _register_pages(runtime: Runtime) -> None:
    drivers: dict[str | None, Driver] = {}

    def driver_for(slug: str | None) -> Driver | None:
        """Memoised: one conversation per game, and `slug=None` is the authoring one."""
        if slug not in drivers:
            match runtime.settings.harness:
                case "claude":
                    drivers[slug] = ClaudeDriver(runtime=runtime, slug=slug)
                case "codex":
                    drivers[slug] = CodexDriver(runtime=runtime, slug=slug)
                case _:
                    return None
        return drivers[slug]

    async def close_drivers() -> None:
        for driver in drivers.values():
            await driver.close()

    app.on_shutdown(close_drivers)  # pyright: ignore[reportUnknownMemberType]

    def apply_settings() -> str | None:
        """Only the memoised map is dropped: a driver mid-turn holds its own reference."""
        refusal = runtime.busy_refusal()
        if refusal is None:
            drivers.clear()
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
            runtime.session(
                LaunchTarget(
                    slug=slug,
                    scenario_id=content_id(scenario),
                    character_id=content_id(character),
                )
            ),
            driver_for(slug),
        )

    @ui.page("/create/{engine}")
    def _create(engine: str) -> None:  # pyright: ignore[reportUnusedFunction]
        character_page(runtime, engine)

    @ui.page("/create-scenario")
    def _create_scenario() -> None:  # pyright: ignore[reportUnusedFunction]
        writer = driver_for(None)
        if writer is not None:
            agent_scenario_page(writer, runtime)
        elif runtime.settings.harness == "external":
            ui.label("Authoring runs in your terminal here: call begin_scenario().")
        else:
            scenario_page(runtime)

    @ui.page("/settings")
    def _settings() -> None:  # pyright: ignore[reportUnusedFunction]
        settings_page(runtime.settings, apply_settings)
