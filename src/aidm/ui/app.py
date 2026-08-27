import logging
from collections.abc import Callable
from functools import partial

from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

from aidm.app.launch import (
    LauncherController,
    LaunchTarget,
    SaveOption,
    as_engine_id,
    load_catalog,
)
from aidm.app.runtime import Runtime
from aidm.config import Settings, load_settings
from aidm.harness.claude import ClaudeDriver
from aidm.harness.codex import CodexDriver
from aidm.harness.driver import Driver
from aidm.harness.opencode import OpencodeDriver
from aidm.harness.pi import PiDriver
from aidm.state.entities import content_id

from .create import agent_scenario_page, character_page, scenario_page
from .game import game_page
from .settings import settings_page
from .widgets import page_header, show_engine_badge

LOGGER = logging.getLogger(__name__)


def home_page(settings: Settings) -> None:
    controller = LauncherController(load_catalog(settings))
    with page_header("AI Dungeon Master", home=False):
        ui.button("Settings", icon="settings", on_click=lambda: ui.navigate.to("/settings")).props(
            "flat color=white"
        )
        ui.space()
        ui.label("Choose your game").classes("text-sm opacity-80")

    with ui.column().classes("w-full q-pa-lg items-center").style("gap: 1.5rem"):
        with ui.column().style("width: min(64rem, 100%); gap: 1.5rem"):
            ui.label("Begin an adventure").classes("text-h4 font-bold")
            ui.label("Choose a scenario, the rules to play it under, then a character.").classes(
                "text-body1 opacity-70"
            )
            _new_game(controller)
            _new_content(controller, settings)
            _saved_games(controller)


def _new_game(controller: LauncherController) -> None:
    @ui.refreshable
    def form() -> None:
        with ui.card().classes("w-full q-pa-lg"):
            ui.label("New or current game").classes("text-h6 font-bold")
            if controller.selected_scenario is None or controller.selected_engine is None:
                ui.label("No playable scenario was found.").classes("text-negative")
                return
            scenario = controller.catalog.scenario(controller.selected_scenario)
            show_engine_badge(controller.catalog.badge(controller.selected_engine))
            ui.select(
                options={option.id: option.title for option in controller.catalog.scenarios},
                value=controller.selected_scenario,
                label="Scenario",
                on_change=_chosen("scenario", controller.choose_scenario, form.refresh),  # pyright: ignore[reportUnknownArgumentType]
            ).classes("w-full")
            ui.label(scenario.subtitle).classes("text-sm opacity-70")
            compatible = controller.compatible_characters()
            ui.select(
                options={option.id: f"{option.title} — {option.subtitle}" for option in compatible},
                value=controller.selected_character,
                label="Character",
                on_change=_chosen("character", controller.choose_character, form.refresh),  # pyright: ignore[reportUnknownArgumentType]
            ).classes("w-full")
            if not compatible:
                ui.label("No character is written for these rules.").classes("text-negative")
                return
            _action(controller)

    form()


def _new_content(controller: LauncherController, settings: Settings) -> None:
    with ui.row().classes("items-center").style("gap: 0.5rem"):
        # Authoring calls a model, and only `external` has neither a key nor an agent to ask.
        if settings.harness == "external":
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
        for option in controller.catalog.engines:
            ui.button(
                option.id,
                icon="person_add",
                on_click=partial(_navigate_create, option.id),
            ).props("outline dense")


def _navigate_create(engine: str) -> None:
    ui.navigate.to(f"/create/{engine}")


def _chosen(
    what: str,
    choose: Callable[[str], None],
    refresh: Callable[[], object],
) -> Callable[[ValueChangeEventArguments[object]], None]:
    """One handler per select: they differ only in the choice they record."""

    def handle(event: ValueChangeEventArguments[object]) -> None:
        LOGGER.info("launcher %s selected: %r", what, event.value)
        if not isinstance(event.value, str):
            ui.notify(f"Choose a {what}.", type="warning")
            return
        try:
            choose(event.value)
        except ValueError as error:
            ui.notify(str(error), type="negative")
            return
        refresh()

    return handle


def _action(controller: LauncherController) -> None:
    target = controller.new_game()
    catalog = controller.catalog
    existing = next((save for save in catalog.saves if save.slug == target.slug), None)
    unreadable = next((save for save in catalog.unreadable if save.slug == target.slug), None)
    blocked = unreadable or (existing if existing is not None and not existing.resumable else None)
    if blocked is not None:
        ui.label(blocked.problem or "This save cannot be resumed.").classes(
            "text-negative text-sm q-mt-md"
        )
        ui.label("Delete or fix the save to continue this game.").classes("text-xs opacity-60")
        return
    ui.button(
        "Continue game" if existing is not None else "Start game",
        icon="play_arrow",
        on_click=lambda: _start(controller),
    ).props("color=primary").classes("q-mt-md")


def _start(controller: LauncherController) -> None:
    LOGGER.info(
        "launcher start requested: scenario=%r character=%r",
        controller.selected_scenario,
        controller.selected_character,
    )
    try:
        target = controller.new_game()
    except ValueError as error:
        ui.notify(str(error), type="warning")
        return
    ui.navigate.to(target.path)


def _saved_games(controller: LauncherController) -> None:
    catalog = controller.catalog
    ui.label("Saved games").classes("text-h5 font-bold q-mt-md")
    if not catalog.saves and not catalog.unreadable:
        ui.label("No saved games yet.").classes("text-body1 opacity-60")
        return
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for saved in catalog.saves:
            _saved_card(controller, saved)
        for broken in catalog.unreadable:
            with ui.card().classes("w-full q-pa-md"):
                ui.label(broken.slug).classes("text-h6 font-bold")
                ui.label(f"Unreadable save: {broken.problem}").classes("text-negative text-sm")


def _saved_card(controller: LauncherController, saved: SaveOption) -> None:
    with ui.card().classes("w-full q-pa-md"):
        with ui.row().classes("w-full items-center").style("gap: 1rem"):
            with ui.column().classes("col").style("gap: 0.25rem"):
                ui.label(saved.scenario_title).classes("text-h6 font-bold")
                ui.label(f"{saved.character_title} · turn {saved.turn}").classes(
                    "text-sm opacity-70"
                )
            show_engine_badge(controller.catalog.badge(saved.engine))
            if saved.resumable:
                ui.button(
                    "Resume",
                    icon="play_arrow",
                    on_click=partial(_resume, controller, saved.slug),
                ).props("color=primary")
            else:
                ui.label(saved.problem or "Save cannot be resumed.").classes(
                    "text-negative text-sm"
                )


def _resume(controller: LauncherController, slug: str) -> None:
    LOGGER.info("launcher resume requested: slug=%s", slug)
    try:
        target = controller.resume(slug)
    except ValueError as error:
        ui.notify(str(error), type="negative")
        return
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
                case "opencode":
                    drivers[slug] = OpencodeDriver(runtime=runtime, slug=slug)
                case "pi":
                    drivers[slug] = PiDriver(runtime=runtime, slug=slug)
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
        home_page(runtime.settings)

    @ui.page("/game/{slug}/{scenario}/{character}/{engine}")
    def _game(  # pyright: ignore[reportUnusedFunction]
        slug: str,
        scenario: str,
        character: str,
        engine: str,
    ) -> None:
        game_page(
            runtime.session(
                LaunchTarget(
                    slug=slug,
                    scenario_id=content_id(scenario),
                    character_id=content_id(character),
                    engine=as_engine_id(engine),
                )
            ),
            driver_for(slug),
        )

    @ui.page("/create/{engine}")
    def _create(engine: str) -> None:  # pyright: ignore[reportUnusedFunction]
        character_page(runtime, as_engine_id(engine))

    @ui.page("/create-scenario")
    def _create_scenario() -> None:  # pyright: ignore[reportUnusedFunction]
        writer = driver_for(None)
        if writer is not None:
            agent_scenario_page(writer, runtime.settings)
        elif runtime.settings.harness == "external":
            ui.label("Authoring runs in your terminal here: call begin_scenario().")
        else:
            scenario_page(runtime.settings)

    @ui.page("/settings")
    def _settings() -> None:  # pyright: ignore[reportUnusedFunction]
        settings_page(runtime.settings, apply_settings)
