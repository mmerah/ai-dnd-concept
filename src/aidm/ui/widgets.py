from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Protocol

from nicegui import ui

from . import theme


class Busy(Protocol):
    busy: bool


def refuse_if_busy(session: Busy) -> bool:
    if not session.busy:
        return False
    ui.notify("Finish the current turn first.", type="warning")
    return True


@asynccontextmanager
async def working(session: Busy) -> AsyncGenerator[None]:
    """A failure is shown to the player and swallowed: the session must never stay busy."""
    session.busy = True
    try:
        yield
    except Exception as error:
        ui.notify(f"{type(error).__name__}: {error}", type="negative", multi_line=True)
    finally:
        session.busy = False


def show_engine_badge(badge: tuple[str, str]) -> None:
    label, colour = badge
    ui.badge(label).props(f"color={colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )


@contextmanager
def page_header(
    title: str, badge: tuple[str, str] | None = None, home: bool = True
) -> Generator[None]:
    theme.apply()
    with ui.header().classes("items-center").style("gap: 1rem"):
        if home:
            ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props(
                "flat color=white round"
            )
        ui.label(title).classes("text-lg font-bold")
        if badge is not None:
            show_engine_badge(badge)
        yield


DM_ICON = "auto_stories"


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


def heading(title: str, *, tight: bool = False) -> None:
    ui.label(title).classes(f"text-xs font-bold opacity-60 {'mt-2' if tight else 'mt-4'}")
