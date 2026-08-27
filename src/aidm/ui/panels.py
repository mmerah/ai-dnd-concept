import json
from collections.abc import Callable

from nicegui import ui

from aidm.app.runtime import (
    AdvancementOffer,
    DraftedAdvance,
    GameSession,
    ThreadSummary,
    attributed_line,
    thread_summaries,
)
from aidm.content.io import SavedGame
from aidm.state.facts import trace_lines, traced
from aidm.state.play import AdvanceApplied, StepTrace, TraceEntry, TurnTrace, WorldExtended
from aidm.turn.context import player_scene

from .widgets import entity_row, heading, labeled_value, refuse_if_busy, working


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
    threads = thread_summaries(session.state)
    if threads:
        heading("Threads")
        for thread in threads:
            _thread_card(thread)


def _thread_card(thread: ThreadSummary) -> None:
    with ui.column().classes("w-full mt-2").style("gap: 0"):
        ui.label(thread.title).classes("text-sm font-bold")
        parts = (thread.status, thread.stage or "", thread.clock)
        ui.label(" · ".join(part for part in parts if part)).classes("text-xs opacity-60")


def journal_panel(session: GameSession) -> None:
    threads = thread_summaries(session.state)

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
            case AdvanceApplied():
                titles.append(f"after turn {turns}: advancement")
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
        case AdvanceApplied(facts=facts):
            _section("ADVANCEMENT", traced(facts))
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


def advancement_panel(session: GameSession, refresh: Callable[[], None]) -> None:
    """The one advancement panel; shown only when the engine plugs in a growth mechanic."""
    if session.settings.code_mode:
        _offered_only(session)
        return
    if session.drafted is not None:
        _review(session, session.drafted, refresh)
        return
    offers = session.offers()
    if not offers:
        ui.label("Nothing is on offer.").classes("opacity-70")
        return
    for offer in offers:
        _summary(offer)
        _intent_form(session, offer, refresh)


def _offered_only(session: GameSession) -> None:
    """Code mode drafts and commits in the MCP server; a second writer here would race it."""
    offers = session.offers()
    if not offers:
        ui.label("Nothing is on offer.").classes("opacity-70")
        return
    for offer in offers:
        _summary(offer)
    ui.label("Ask for it in the terminal.").classes("text-sm opacity-60 mt-3")


def _summary(offer: AdvancementOffer) -> None:
    ui.label(offer.prompt).classes("text-sm font-bold")
    if offer.text:
        ui.label(offer.text).classes("text-sm opacity-70 whitespace-pre-wrap")


def _intent_form(
    session: GameSession, offer: AdvancementOffer, refresh: Callable[[], None]
) -> None:
    box = ui.textarea("How do you want to grow?").classes("w-full mt-3").props("outlined")

    async def propose() -> None:
        intent = (box.value or "").strip()
        if not intent:
            ui.notify("Say how you want to grow first.", type="warning")
            return
        # Checked at click time: a turn may have started after the panel rendered.
        if refuse_if_busy(session):
            return
        async with working(session):
            session.drafted = DraftedAdvance(
                offer=offer, proposal=await session.propose(offer, intent)
            )
        refresh()

    ui.button("Propose", on_click=propose).props("color=primary")


def _review(session: GameSession, drafted: DraftedAdvance, refresh: Callable[[], None]) -> None:
    ui.label("Proposed changes").classes("text-sm font-bold mt-3")
    try:
        lines = trace_lines(session.preview(drafted))
    except ValueError as stale:
        # A turn since the proposal may have changed the character from under the draft.
        lines = [f"This proposal no longer applies: {stale}. Discard it and propose again."]
    for line in lines:
        ui.label(line).classes("text-sm whitespace-pre-wrap")

    def discard() -> None:
        session.drafted = None
        refresh()

    def confirm() -> None:
        if refuse_if_busy(session):
            return
        try:
            _ = session.apply_proposal(drafted)
        except ValueError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        session.drafted = None
        refresh()

    with ui.row().classes("w-full mt-3").style("gap: 0.75rem"):
        ui.button("Discard", on_click=discard).props("flat")
        ui.button("Confirm", on_click=confirm).props("color=primary")


def state_panel(session: GameSession) -> None:
    ui.code(
        SavedGame.from_game(session.state).model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
