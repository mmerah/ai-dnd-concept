import logging
from collections.abc import Callable
from functools import partial

from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

from aidm.app.launch import LauncherCatalog, LaunchTarget, PackEntry, SaveOption
from aidm.app.mcp import MOUNT_PATH, MountedLifespan, endpoint
from aidm.app.runtime import Runtime
from aidm.config import SERVER_HOST, read_settings
from aidm.core.entities import EngineId, Refusal, Slug, content_id
from aidm.ui import theme
from aidm.ui.create import character_page, new_pack_page, scenario_page
from aidm.ui.dice import DICE_SOUND, DICE_SOUND_ROUTE
from aidm.ui.game import game_page
from aidm.ui.packs import PACK_ROUTE, pack_page, pack_path
from aidm.ui.settings import settings_page
from aidm.ui.widgets import (
    GAME_ROUTE,
    game_path,
    heading,
    page_body,
    page_header,
    page_intro,
    section,
)

LOGGER = logging.getLogger(__name__)


class LaunchForm:
    def __init__(self, catalog: LauncherCatalog) -> None:
        self.catalog = catalog
        self.scenario_id: Slug = catalog.scenarios[0].id
        self.character_id: Slug | None = None

    def choose_scenario(self, event: ValueChangeEventArguments[str]) -> None:
        self.scenario_id = content_id(event.value)
        self.form.refresh()

    def choose_character(self, event: ValueChangeEventArguments[str]) -> None:
        self.character_id = content_id(event.value)
        self.form.refresh()

    @ui.refreshable_method
    def form(self) -> None:
        catalog = self.catalog
        scenario = catalog.scenario(self.scenario_id)
        theme.set_look(scenario.look)
        ui.select(
            options={entry.id: f"{entry.name} · {entry.rules}" for entry in catalog.scenarios},
            value=self.scenario_id,
            label="Scenario",
            on_change=self.choose_scenario,
        )
        ui.label(scenario.brief).classes("text-sm opacity-70")
        characters = {
            entry.id: f"{entry.name} — {entry.brief}"
            for entry in catalog.characters_for(scenario.engine)
        }
        chosen = (
            self.character_id if self.character_id in characters else next(iter(characters), None)
        )
        ui.select(
            options=characters,
            value=chosen,
            label="Character",
            on_change=self.choose_character,
        )
        if chosen is None:
            ui.label("No character is written for these rules.").classes("text-negative")
            return
        target = catalog.target(self.scenario_id, chosen)
        if target.slug in catalog.unresumable:
            ui.label(
                f"A save file exists at {target.slug!r} and cannot be resumed. "
                "Nothing is deleted or migrated."
            ).classes("text-negative")
            return
        started = any(save.target.slug == target.slug for save in catalog.saves)
        ui.button(
            "Continue game" if started else "Start game",
            icon="play_arrow",
            on_click=partial(_open_game, target),
        ).props("color=primary").classes("q-mt-md")


def home_page(runtime: Runtime) -> None:
    catalog = LauncherCatalog.read(runtime.library, runtime.store, runtime.engines)
    with page_header("AI Dungeon Master", home=False):
        ui.button("Settings", icon="settings", on_click=lambda: ui.navigate.to("/settings")).props(
            "flat"
        )
        ui.space()
        ui.label("Choose your game").classes("text-sm opacity-80 gt-xs")

    with page_body():
        page_intro(
            "Adventure",
            "Begin an adventure",
            "Choose a scenario, then a character written for its rules.",
        )
        with section("New or current game"):
            if catalog.scenarios:
                LaunchForm(catalog).form()
            else:
                ui.label("No playable scenario was found.").classes("text-negative")
        _new_content()
        _saved_games(catalog)
        _packs(catalog)


def mount(runtime: Runtime) -> None:
    """Puts the MCP endpoint, the dice sound, the lifespan hooks and every page on the app."""
    plain_pages: tuple[tuple[str, Callable[[Runtime], None]], ...] = (
        ("/", home_page),
        ("/create", character_page),
        ("/scenario", scenario_page),
        ("/pack", new_pack_page),
        ("/settings", lambda runtime: settings_page(runtime.settings)),
    )
    asgi, manager = endpoint(runtime.gate)
    app.mount(MOUNT_PATH, asgi)
    app.add_static_file(local_file=DICE_SOUND, url_path=DICE_SOUND_ROUTE)
    lifespan = MountedLifespan(manager)
    app.on_startup(lifespan.start)  # pyright: ignore[reportUnknownMemberType]
    app.on_shutdown(lifespan.stop)  # pyright: ignore[reportUnknownMemberType]
    app.on_shutdown(runtime.close)  # pyright: ignore[reportUnknownMemberType]
    for route, page in plain_pages:
        ui.page(route)(partial(page, runtime))
    ui.page(GAME_ROUTE)(partial(_game, runtime))
    ui.page(PACK_ROUTE)(partial(_pack, runtime))


def start() -> None:
    # Without a handler the root logger drops every INFO record, spawns included.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = read_settings()
    except Refusal as broken:
        raise SystemExit(f"settings: {broken}") from None
    mount(Runtime(settings))
    theme.install()
    ui.run(  # pyright: ignore[reportUnknownMemberType]
        title="AI Dungeon Master",
        host=SERVER_HOST,
        port=settings.server_port,
        reload=False,
        show=False,
    )


def _new_content() -> None:
    with ui.row().classes("items-center game-gap-lg"):
        ui.button(
            "New character", icon="person_add", on_click=lambda: ui.navigate.to("/create")
        ).props("outline dense")
        ui.button(
            "New scenario", icon="auto_stories", on_click=lambda: ui.navigate.to("/scenario")
        ).props("outline dense")
        ui.button("New pack", icon="auto_fix_high", on_click=lambda: ui.navigate.to("/pack")).props(
            "outline dense"
        )


def _saved_games(catalog: LauncherCatalog) -> None:
    heading("Saved games")
    if not catalog.saves:
        ui.label("No saved games yet.").classes("text-body1 opacity-60")
        return
    with ui.column().classes("w-full game-gap-xl"):
        for saved in catalog.saves:
            _saved_card(saved)


def _packs(catalog: LauncherCatalog) -> None:
    heading("Packs")
    with ui.column().classes("w-full game-gap-md"):
        for pack in catalog.packs:
            with ui.row().classes("w-full items-center game-gap-lg"):
                ui.label(pack.name).classes("game-title")
                ui.label(pack.tables).classes("text-sm opacity-70 col")
                ui.badge(pack.rules)
                if pack.written:
                    ui.badge("Written").props("color=secondary")
                ui.button(
                    "Edit" if pack.written else "View",
                    icon="edit" if pack.written else "visibility",
                    on_click=partial(_open_pack, pack),
                ).props("outline dense")


def _saved_card(saved: SaveOption) -> None:
    with (
        ui.card().classes("w-full"),
        ui.row().classes("w-full items-center game-gap-2xl"),
    ):
        with ui.column().classes("col game-gap-xs"):
            ui.label(saved.scenario_label).classes("text-h6 game-title")
            ui.label(
                f"{saved.character_label} · turn {saved.turn}"
                + (f" · {saved.where}" if saved.where else "")
            ).classes("text-sm opacity-70")
            with ui.row().classes("game-gap-lg"):
                ui.badge(saved.rules)
        ui.button(
            "Resume",
            icon="play_arrow",
            on_click=partial(_open_game, saved.target),
        ).props("color=primary").classes("col-12 col-sm-auto")


def _open_game(target: LaunchTarget) -> None:
    LOGGER.info("launcher opening %r", target.slug)
    ui.navigate.to(game_path(target))


def _open_pack(entry: PackEntry) -> None:
    ui.navigate.to(pack_path(entry.engine, entry.id))


def _refused_page(message: str) -> None:
    page_header("AI Dungeon Master")
    with (
        page_body(),
        ui.card().classes("w-full"),
        ui.column().classes("items-center game-gap-2xl"),
    ):
        ui.label(message).classes("text-body1")
        ui.button("Home", icon="home", on_click=lambda: ui.navigate.to("/")).props("color=primary")


async def _game(runtime: Runtime, scenario: str, character: str) -> None:
    try:
        session = runtime.session(
            LaunchTarget(scenario_id=content_id(scenario), character_id=content_id(character))
        )
    except Refusal as refused:
        _refused_page(str(refused))
        return
    # Tab storage (the composer draft) is readable only after the handshake.
    await ui.context.client.connected()
    game_page(session)


def _pack(runtime: Runtime, engine: str, pack: str) -> None:
    try:
        pack_page(runtime, EngineId(engine), content_id(pack))
    except Refusal as refused:
        _refused_page(str(refused))
