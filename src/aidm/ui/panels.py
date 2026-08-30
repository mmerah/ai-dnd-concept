from nicegui import ui

from aidm.app.runtime import GameSession
from aidm.state.entities import Entity
from aidm.state.model import Game, Thread
from aidm.state.play import Line
from aidm.world.scene import placement
from aidm.world.topology import children, location_of

from .widgets import entity_row, heading


def sheet_panel(session: GameSession) -> None:
    player = session.state.player
    entity_row(session.icon(player.id), player.name, player.brief)
    if player.traits:
        heading("Traits")
        with ui.row().classes("w-full items-center").style("gap: 0.35rem"):
            for trait in player.traits:
                badge = ui.badge(trait.name).props("color=grey-8 outline")
                if trait.text:
                    badge.tooltip(trait.text)
    carried = children(session.state.world, player.id, "item")
    if carried:
        heading("Carrying")
        for item in carried:
            entity_row(session.icon(item.id), item.name, item.brief)


def _known_elsewhere(state: Game) -> tuple[Entity, ...]:
    """Met canon that is not here: empty for an engine whose world has no elsewhere."""
    here = state.player.parent_id
    return tuple(
        entity
        for entity in state.world.entities.values()
        if entity.known
        and entity.id != state.player_id
        and location_of(state.world, entity) not in (None, here)
    )


def _thread_card(thread: Thread) -> None:
    with ui.column().classes("w-full mt-2").style("gap: 0"):
        ui.label(thread.title).classes("text-sm font-bold")
        ui.label(thread.status).classes("text-xs opacity-60")


def _attributed_line(state: Game, line: Line) -> str:
    """A speaker is named, because a bare quote reads as narration once the bubbles are gone."""
    speaker = None if line.speaker_id is None else state.world.require(line.speaker_id)
    return line.text if speaker is None else f"**{speaker.name}:** {line.text}"


def journal_panel(session: GameSession) -> None:
    threads = session.state.world.threads.values()
    if threads:
        heading("Threads")
        for thread in threads:
            _thread_card(thread)
    world = session.state.world
    met = {one.id: one for one in world.entities.values() if one.known}
    if elsewhere := _known_elsewhere(session.state):
        heading("What you know of")
        for entity in elsewhere:
            where = placement(met, world.party, session.state.player_id, entity)
            entity_row(session.icon(entity.id), entity.name, where or entity.brief)
    heading("Chronicle")
    for number, exchange in reversed(list(enumerate(session.state.history, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            for line in exchange.lines:
                ui.markdown(_attributed_line(session.state, line)).classes("text-sm")


def state_panel(session: GameSession) -> None:
    ui.code(
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
