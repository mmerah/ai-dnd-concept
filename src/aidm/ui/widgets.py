from collections.abc import Awaitable, Callable, Generator, Sequence
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from nicegui import ui

from aidm.app.launch import LaunchTarget
from aidm.core.entities import EngineId
from aidm.core.play import DecisionOption
from aidm.ui import theme

DM_ICON = "auto_stories"
GAME_ROUTE = "/game/{scenario}/{character}"


def game_path(target: LaunchTarget) -> str:
    return GAME_ROUTE.format(scenario=target.scenario_id, character=target.character_id)


@contextmanager
def page_header(
    title: str, badge: str | None = None, home: bool = True, *, engine: EngineId | None = None
) -> Generator[None]:
    theme.apply(engine)
    with ui.header().classes("items-center no-wrap"):
        if home:
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props("flat round")
        ui.label(title).classes("game-title ellipsis")
        if badge is not None:
            ui.badge(badge).classes("gt-xs")
        yield


@contextmanager
def page_body() -> Generator[None]:
    """The centred column every page but the game puts its content in."""
    with (
        ui.column().classes("w-full q-pa-lg items-center"),
        ui.column().classes("w-full").style("max-width: var(--game-measure); gap: 1.25rem"),
    ):
        yield


def page_intro(eyebrow: str, title: str, lead: str) -> None:
    with ui.column().style("gap: .2rem"):
        ui.label(eyebrow).classes("game-eyebrow")
        ui.label(title).classes("text-h4 game-title")
        ui.label(lead).classes("text-body1 game-lead")


@contextmanager
def section(title: str, *, classes: str = "") -> Generator[None]:
    """A card with the eyebrow that names it: the sidebar panels, the launcher, settings tabs."""
    with ui.card().classes(f"w-full {classes}").style("gap: .5rem"):
        heading(title)
        yield


def heading(title: str) -> None:
    ui.label(title).classes("game-eyebrow")


def entity_row(icon: Path | None, name: str, sub: str) -> None:
    with ui.element("div").classes("game-entity"):
        avatar(icon, name)
        with ui.column().style("gap: 0"):
            ui.label(name).classes("game-entity-name game-title")
            ui.label(sub).classes("game-entity-sub")


def avatar(icon: Path | None, name: str | None) -> None:
    with ui.avatar(size="42px", color=None).classes(
        "game-avatar" + (" game-avatar-dm" if name is None else "")
    ):
        if icon is not None:
            ui.image(icon)
        elif name is None:
            ui.icon(DM_ICON)
        else:
            ui.label(name[:1].upper()).classes("text-subtitle1")


def labeled_value(label: str, value: str) -> None:
    with ui.element("div").classes("game-stat" + (" game-stat-long" if len(value) > 28 else "")):
        ui.label(label).classes("game-stat-label")
        ui.label(value or "—").classes("game-stat-value")


def decision_widget(
    prompt: str,
    options: Sequence[DecisionOption],
    answer: Callable[[str], Awaitable[None]],
) -> None:
    ui.label(prompt).classes("text-base whitespace-pre-wrap")
    if not options:
        return
    with ui.row().classes("w-full items-start").style("gap: 0.5rem"):
        for option in options:
            # A label in the button's own slot sits beside the detail, not above it.
            with (
                ui.button(on_click=partial(answer, option.id))
                .props("outline")
                .style("min-height: 44px"),
                ui.column().style("gap: 0"),
            ):
                ui.label(option.label)
                if option.detail:
                    ui.label(option.detail).classes("text-xs opacity-70")
