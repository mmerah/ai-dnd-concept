import json

from nicegui import ui

from aidm.app.runtime import GameSession, attributed_line
from aidm.state.facts import traced
from aidm.state.model import Thread
from aidm.state.play import StepTrace, TraceEntry, TurnTrace, WorldExtended
from aidm.turn.context import player_scene

from .widgets import entity_row, heading, labeled_value


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
    for label, value in session.engine.sheet_rows(session.state):
        labeled_value(label, value)
    inventory = player_scene(session.state).inventory
    if inventory:
        heading("Carrying")
        for item in inventory:
            entity_row(session.icon(item.id), item.name, item.brief)
    threads = session.state.world.threads
    if threads:
        heading("Threads")
        for thread in threads:
            _thread_card(thread)


def _thread_card(thread: Thread) -> None:
    with ui.column().classes("w-full mt-2").style("gap: 0"):
        ui.label(thread.title).classes("text-sm font-bold")
        ui.label(thread.status).classes("text-xs opacity-60")


def journal_panel(session: GameSession) -> None:
    threads = session.state.world.threads

    def export() -> None:
        ui.notify(f"Journal written to {session.export_journal()}")

    ui.button("Export markdown", icon="download", on_click=export).props("flat dense")
    if threads:
        heading("Threads")
        for thread in threads:
            _thread_card(thread)
    scene = player_scene(session.state)
    if scene.known_elsewhere:
        heading("What you know of")
        for entity in scene.known_elsewhere:
            entity_row(
                session.icon(entity.id), entity.name, scene.placement_of(entity) or entity.brief
            )
    heading("Chronicle")
    for number, exchange in reversed(list(enumerate(session.state.history, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            for line in exchange.lines:
                ui.markdown(attributed_line(session.state, line)).classes("text-sm")


def trace_panel(session: GameSession) -> None:
    entries = session.entries
    if not entries:
        ui.label("No turns yet this session.").classes("opacity-60")
    turns = 0
    titles: list[str] = []
    for entry in entries:
        match entry:
            case TurnTrace(prompt=prompt):
                turns += 1
                titles.append(f"turn {turns}: {prompt}")
            case WorldExtended():
                titles.append(f"after turn {turns}: the world grew")
    for index, entry in reversed(list(enumerate(entries))):
        with ui.expansion(titles[index], value=index == len(entries) - 1):
            _entry_trace(entry)


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


def _entry_trace(entry: TraceEntry) -> None:
    match entry:
        case WorldExtended(facts=facts):
            _section("THE WORLD GREW", traced(facts))
        case TurnTrace():
            _turn_trace(entry)


def _turn_trace(turn: TurnTrace) -> None:
    for step in turn.steps:
        _section(step.name.upper(), _output(step))
    _section("FACTS (private)", traced(turn.facts))
    with ui.expansion("what each role was shown").classes("w-full mt-3"):
        for step in turn.steps:
            _section(step.name.upper(), step.prompt)


def _output(step: StepTrace) -> str:
    match step.output:
        case str() as text:
            return text
        case body:
            return json.dumps(body, indent=2)


def state_panel(session: GameSession) -> None:
    ui.code(
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
