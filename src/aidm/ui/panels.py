from nicegui import ui

from aidm.app.runtime import GameService
from aidm.state.entities import EntityId

from .widgets import entity_row, heading, labeled_value


def sheet_panel(session: GameService) -> None:
    view = session.view().player
    entity_row(session.icon(EntityId(view.player.id)), view.player.name, view.player.brief)
    if view.traits:
        heading("Traits")
        with ui.row().classes("w-full items-center").style("gap: 0.35rem"):
            for name, text in view.traits:
                badge = ui.badge(name).props("color=grey-8 outline")
                if text:
                    badge.tooltip(text)
    for label, text in view.sheet:
        labeled_value(label, text)
    if view.carrying:
        heading("Carrying")
        for item in view.carrying:
            entity_row(session.icon(EntityId(item.id)), item.name, item.brief)


def journal_panel(session: GameService) -> None:
    view = session.view().player
    if view.threads:
        heading("Threads")
        for title, status in view.threads:
            with ui.column().classes("w-full mt-2").style("gap: 0"):
                ui.label(title).classes("text-sm font-bold")
                ui.label(status).classes("text-xs opacity-60")
    if view.scenes:
        heading("Scenes")
        for title in view.scenes:
            ui.label(title).classes("text-sm")
    heading("Chronicle")
    for number, exchange in reversed(list(enumerate(session.state.history, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            # A speaker is named, because a bare quote reads as narration without bubbles.
            for line in exchange.lines:
                who = line.speaker
                said = line.text if who is None else f"**{who.name}:** {line.text}"
                ui.markdown(said).classes("text-sm")


def state_panel(session: GameService) -> None:
    ui.code(
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
