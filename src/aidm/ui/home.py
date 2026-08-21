import logging
from collections.abc import Callable
from functools import partial

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from aidm.app.launch import (
    LauncherController,
    SaveOption,
    as_engine_id,
    load_catalog,
)
from aidm.config import Settings

from .panels import page_header, show_engine_badge

LOGGER = logging.getLogger(__name__)


def home_page(config: Settings) -> None:
    controller = LauncherController(load_catalog(config))
    with page_header("AI Dungeon Master", home=False):
        ui.space()
        ui.label("Choose your game").classes("text-sm opacity-80")

    with ui.column().classes("w-full q-pa-lg items-center").style("gap: 1.5rem"):
        with ui.column().style("width: min(64rem, 100%); gap: 1.5rem"):
            ui.label("Begin an adventure").classes("text-h4 font-bold")
            ui.label("Choose a scenario, the rules to play it under, then a character.").classes(
                "text-body1 opacity-70"
            )
            _new_game(controller)
            _new_content(controller)
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
            ui.select(
                options={engine: engine for engine in controller.available_engines()},
                value=controller.selected_engine,
                label="Rules",
                on_change=_chosen(  # pyright: ignore[reportUnknownArgumentType]
                    "engine",
                    lambda value: controller.choose_engine(as_engine_id(value)),
                    form.refresh,
                ),
            ).classes("w-full")
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


def _new_content(controller: LauncherController) -> None:
    with ui.row().classes("items-center").style("gap: 0.5rem"):
        ui.button(
            "New scenario", icon="auto_stories", on_click=lambda: ui.navigate.to("/create-scenario")
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
