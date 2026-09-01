from nicegui import ui

from aidm.app.runtime import GameService
from aidm.core.entities import EntityId
from aidm.core.views import PlayerView, ThreadRow

from .widgets import entity_row, heading, labeled_value

NO_WAY_ON = "The way on could not be written. You are still where you were."


def scene_sidebar(session: GameService) -> None:
    view = session.player_view()
    with ui.column().classes("w-full").style("gap: 0.75rem"):
        _scene_card(view, session.write_failure)
        _cast_card(session, view)
        _sheet_card(session, view)
        _threads_card(view.threads)


def journal_panel(session: GameService) -> None:
    view = session.player_view()
    if view.trail:
        heading("Trail", tight=True)
        for title in view.trail:
            ui.label(title).classes("text-sm")
    heading("Chronicle")
    played = session.engine.history(session.state)
    for number, exchange in reversed(list(enumerate(played, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            # A speaker is named, because a bare quote reads as narration without bubbles.
            for line in exchange.lines:
                who = line.speaker
                said = line.text if who is None else f"**{who.name}:** {line.text}"
                ui.markdown(said).classes("text-sm")


def _scene_card(view: PlayerView, failure: str) -> None:
    with ui.column().classes("game-card w-full"):
        heading("This scene", tight=True)
        ui.label(view.focus).classes("text-sm mt-1")
        for label, text in view.world_rows:
            labeled_value(label, text)
        if failure:
            ui.label(NO_WAY_ON).classes("text-xs text-warning mt-1")


def _cast_card(session: GameService, view: PlayerView) -> None:
    with ui.column().classes("game-card w-full"):
        heading("Here", tight=True)
        entity_row(
            session.icon(EntityId(view.player.id)), f"{view.player.name} (you)", view.player.brief
        )
        for one in view.present:
            entity_row(session.icon(EntityId(one.id)), one.name, one.brief)
        if view.companions:
            labeled_value("Travelling with", ", ".join(view.companions))


def _sheet_card(session: GameService, view: PlayerView) -> None:
    with ui.column().classes("game-card w-full"):
        heading("Sheet", tight=True)
        for label, text in view.sheet:
            labeled_value(label, text)
        if view.traits:
            with ui.row().classes("w-full items-center mt-2").style("gap: 0.35rem"):
                for name, text in view.traits:
                    badge = ui.badge(name).props("color=grey-8 outline")
                    if text:
                        badge.tooltip(text)
        labeled_value("Carrying", "" if view.carrying else "nothing")
        for item in view.carrying:
            entity_row(session.icon(EntityId(item.id)), item.name, item.brief)


def _threads_card(threads: tuple[ThreadRow, ...]) -> None:
    with ui.column().classes("game-card w-full"):
        heading("Threads", tight=True)
        if not threads:
            ui.label("nothing open").classes("text-sm opacity-60 mt-2")
        for one in threads:
            with ui.column().classes("w-full mt-2").style("gap: 0"):
                with ui.row().classes("w-full items-baseline no-wrap").style("gap: 0.4rem"):
                    ui.label(one.title).classes("text-sm font-bold")
                    if one.status != "active":
                        ui.badge(one.status).props("color=grey-8 outline").classes("text-xs")
                if one.note:
                    ui.label(one.note).classes("text-xs opacity-70")
