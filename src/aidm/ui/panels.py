from collections.abc import Awaitable, Callable
from functools import partial

from nicegui import ui

from aidm.app.runtime import GameService

from .widgets import entity_row, heading, labeled_value

NO_WAY_ON = "The way on could not be written. You are still where you were."


@ui.refreshable
def scene_sidebar(session: GameService, move_on: Callable[[str], Awaitable[None]]) -> None:
    view = session.player_view()
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        for panel in view.panels:
            with ui.column().classes("game-card w-full"):
                heading(panel.title, tight=True)
                if not panel.rows:
                    ui.label("nothing").classes("text-sm opacity-60 mt-2")
                for row in panel.rows:
                    if row.intent:
                        ui.button(row.label, on_click=partial(move_on, row.intent)).props(
                            "no-caps outline dense"
                        )
                        if row.detail:
                            ui.label(row.detail).classes("text-xs opacity-70")
                    elif row.icon_id is not None:
                        entity_row(session.icon(row.icon_id), row.label, row.detail)
                    elif row.detail:
                        labeled_value(row.label, row.detail)
                    else:
                        ui.label(row.label).classes("text-sm mt-1")
        if session.write_failure:
            ui.label(NO_WAY_ON).classes("text-xs text-warning mt-1")


@ui.refreshable
def journal_panel(session: GameService) -> None:
    heading("Chronicle")
    played = session.engine.history(session.state)
    for number, exchange in reversed(list(enumerate(played, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            # A speaker is named, because a bare quote reads as narration without bubbles.
            for line in exchange.lines:
                who = line.speaker
                said = line.text if who is None else f"**{who.name}:** {line.text}"
                ui.markdown(said).classes("text-sm")
