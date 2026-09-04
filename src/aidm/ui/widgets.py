from collections.abc import AsyncGenerator, Awaitable, Callable, Generator, Sequence
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from pathlib import Path

from nicegui import ui

from aidm.app.launch import LaunchTarget
from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption
from aidm.ui import theme

DM_ICON = "auto_stories"
GAME_ROUTE = "/game/{scenario}/{character}"


def game_path(target: LaunchTarget) -> str:
    return GAME_ROUTE.format(scenario=target.scenario_id, character=target.character_id)


@asynccontextmanager
async def working() -> AsyncGenerator[None]:
    """A refusal or an OS error is shown to the player; a bug propagates."""
    try:
        yield
    except (OSError, Refusal) as error:
        ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)


@contextmanager
def page_header(title: str, badge: str | None = None, home: bool = True) -> Generator[None]:
    theme.apply()
    with ui.header().classes("items-center").style("gap: 1rem"):
        if home:
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                "flat color=white round"
            )
        ui.label(title).classes("text-lg font-bold")
        if badge is not None:
            ui.badge(badge).props("color=primary text-color=white").classes(
                "text-sm font-bold q-px-md q-py-sm"
            )
        yield


def entity_row(icon: Path | None, name: str, sub: str) -> None:
    with ui.row().classes("w-full items-center no-wrap mt-2").style("gap: 0.5rem"):
        avatar(icon, name)
        with ui.column().style("gap: 0"):
            ui.label(name).classes("text-sm font-bold")
            ui.label(sub).classes("text-xs opacity-70")


def avatar(icon: Path | None, name: str | None) -> None:
    """`name` is None for the DM, whose avatar is the one shipped material icon."""
    with ui.avatar(color="grey-8", size="42px").classes("q-mx-sm"):
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
    with ui.row().classes("w-full items-center").style("gap: 0.5rem"):
        for option in options:
            button = ui.button(option.label, on_click=partial(answer, option.id)).props(
                "no-caps outline"
            )
            if option.detail:
                button.tooltip(option.detail)


def heading(title: str, *, tight: bool = False) -> None:
    ui.label(title).classes(f"text-xs font-bold opacity-60 {'mt-2' if tight else 'mt-4'}")
