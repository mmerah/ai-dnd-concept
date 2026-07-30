import logging
from collections.abc import Callable

from aidm.application.launcher import (
    EngineStampLookup,
    LauncherController,
    SaveOption,
    load_catalog,
)
from aidm.config import Settings
from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from .components.engine import show_engine_badge

LOGGER = logging.getLogger(__name__)


def home_page(config: Settings, installed_stamp: EngineStampLookup) -> None:
    controller = LauncherController(load_catalog(config, installed_stamp))
    with ui.header().classes("items-center").style("gap: 1rem"):
        ui.label("AI Dungeon Master").classes("text-lg font-bold")
        ui.space()
        ui.label("Choose your game").classes("text-sm opacity-80")

    with ui.column().classes("w-full q-pa-lg items-center").style("gap: 1.5rem"):
        with ui.column().style("width: min(64rem, 100%); gap: 1.5rem"):
            ui.label("Begin an adventure").classes("text-h4 font-bold")
            ui.label("Choose a scenario, then a character built for its rules engine.").classes(
                "text-body1 opacity-70"
            )
            _new_game(controller)
            _saved_games(controller)


def _new_game(controller: LauncherController) -> None:
    @ui.refreshable
    def form() -> None:
        with ui.card().classes("w-full q-pa-lg"):
            ui.label("New or current game").classes("text-h6 font-bold")
            if controller.selected_scenario is None:
                ui.label("No scenarios were found.").classes("text-negative")
                return
            scenario = controller.catalog.scenario(controller.selected_scenario)
            show_engine_badge(scenario.engine)
            ui.select(
                options={option.name: option.title for option in controller.catalog.scenarios},
                value=controller.selected_scenario,
                label="Scenario",
                on_change=choose_scenario,  # pyright: ignore[reportUnknownArgumentType]
            ).classes("w-full")
            ui.label(scenario.premise).classes("text-sm opacity-70")
            compatible = controller.compatible_characters()
            ui.select(
                options={option.name: f"{option.title} — {option.brief}" for option in compatible},
                value=controller.selected_character,
                label="Character",
                on_change=choose_character,  # pyright: ignore[reportUnknownArgumentType]
            ).classes("w-full")
            if not compatible:
                ui.label("No character is compatible with this scenario's engine.").classes(
                    "text-negative"
                )
                return
            _action(controller)

    def choose_scenario(event: ValueChangeEventArguments[object]) -> None:
        LOGGER.info("launcher scenario selected: %r", event.value)
        if not isinstance(event.value, str):
            ui.notify("Choose a scenario.", type="warning")
            return
        try:
            controller.choose_scenario(event.value)
        except ValueError as error:
            ui.notify(str(error), type="negative")
            return
        form.refresh()

    def choose_character(event: ValueChangeEventArguments[object]) -> None:
        LOGGER.info("launcher character selected: %r", event.value)
        if not isinstance(event.value, str):
            ui.notify("Choose a character.", type="warning")
            return
        try:
            controller.choose_character(event.value)
        except ValueError as error:
            ui.notify(str(error), type="negative")
            return
        form.refresh()

    form()


def _action(controller: LauncherController) -> None:
    target = controller.new_game()
    existing = next(
        (save for save in controller.catalog.saves if save.slug == target.slug),
        None,
    )
    if existing is not None and not existing.resumable:
        ui.label(existing.problem or "This game's save cannot be resumed.").classes(
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
            show_engine_badge(saved.engine)
            if saved.resumable:
                ui.button(
                    "Resume",
                    icon="play_arrow",
                    on_click=_resume_handler(controller, saved.slug),
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


def _resume_handler(controller: LauncherController, slug: str) -> Callable[[], None]:
    return lambda: _resume(controller, slug)
