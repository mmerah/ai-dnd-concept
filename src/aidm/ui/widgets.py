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
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                "flat color=white round"
            )
        ui.label(title).classes("text-lg font-bold ellipsis game-title")
        if badge is not None:
            ui.badge(badge).props("color=primary text-color=white").classes(
                "text-sm font-bold q-px-md q-py-sm gt-xs"
            )
        yield


def entity_row(icon: Path | None, name: str, sub: str) -> None:
    with ui.row().classes("w-full items-center no-wrap mt-2").style("gap: 0.5rem"):
        avatar(icon, name)
        with ui.column().style("gap: 0"):
            ui.label(name).classes("text-sm font-bold")
            ui.label(sub).classes("text-xs opacity-70")


def avatar(icon: Path | None, name: str | None) -> None:
    with ui.avatar(color="grey-8", size="42px").classes(
        "q-mx-sm game-avatar" + (" game-avatar-dm" if name is None else "")
    ):
        if icon is not None:
            ui.image(icon)
        elif name is None:
            ui.icon(DM_ICON)
        else:
            ui.label(name[:1].upper()).classes("text-subtitle1")


def labeled_value(label: str, value: str) -> None:
    with ui.row().classes("w-full items-baseline no-wrap mt-2").style("gap: 0.5rem"):
        ui.label(label).classes("text-xs font-bold opacity-60")
        ui.label(value or "—").classes("text-sm")


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
                .props("no-caps outline")
                .style("min-height: 44px"),
                ui.column().style("gap: 0"),
            ):
                ui.label(option.label)
                if option.detail:
                    ui.label(option.detail).classes("text-xs opacity-70")


def heading(title: str, *, tight: bool = False) -> None:
    ui.label(title).classes(f"text-xs font-bold game-heading {'mt-2' if tight else 'mt-4'}")
