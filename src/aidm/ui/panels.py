import json
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from pathlib import Path

from nicegui import ui

from aidm.app.session import Drafted, GameSession, Offer
from aidm.app.views import (
    JournalView,
    ThreadSummary,
    attributed_line,
    played_turns,
    player_scene,
    thread_summaries,
)
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.facts import Fact
from aidm.state.turn import Applied, StepTrace, TraceEntry, Turn
from aidm.turn.scene import Exit

from .busy import refuse_if_busy, working


def show_engine_badge(badge: tuple[str, str]) -> None:
    label, colour = badge
    ui.badge(label).props(f"color={colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )


@contextmanager
def page_header(
    title: str, badge: tuple[str, str] | None = None, home: bool = True
) -> Generator[None]:
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


def scene_header(session: GameSession, fill_composer: Callable[[str], None]) -> None:
    scene = player_scene(session.state)
    ui.label(scene.location.name).classes("text-h6 font-bold")
    ui.label(scene.location.brief).classes("text-sm opacity-70")
    art = session.scene_art()
    if art is not None:
        ui.image(art).classes("w-full rounded-borders")
    elif session.scene_pending():
        ui.skeleton().classes("w-full rounded-borders").style("height: 8rem")
    _heading("Here now")
    if not scene.here:
        ui.label("Nobody but you.").classes("text-sm opacity-70")
    for entity in scene.here:
        _entity_row(session.icon(entity.id), entity.name, entity.brief)
    _heading("Exits")
    if not scene.exits:
        ui.label("None found yet.").classes("text-sm opacity-70")
    for exit in scene.exits:
        _exit_button(exit, fill_composer)


def _entity_row(icon: Path | None, name: str, sub: str) -> None:
    with ui.row().classes("w-full items-center no-wrap mt-2").style("gap: 0.5rem"):
        _avatar(icon, name)
        with ui.column().style("gap: 0"):
            ui.label(name).classes("text-sm font-bold")
            ui.label(sub).classes("text-xs opacity-70")


def _exit_button(exit: Exit, fill_composer: Callable[[str], None]) -> None:
    """The button writes the move into the composer; the player still sends it themselves."""
    label = f"{exit.name} (locked)" if exit.locked else exit.name
    ui.button(
        label, icon="arrow_forward", on_click=lambda: fill_composer(f"Go to {exit.name}")
    ).props("flat dense no-caps align=left").classes("w-full")


def chat(session: GameSession) -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    for played in played_turns(session.state.history, session.entries):
        _bubble(session, PLAYER_ID, played.exchange.prompt, sent=True)
        for line in played.exchange.lines:
            _bubble(session, line.speaker_id, line.text, sent=False)
        if played.outcomes:
            ui.label(" · ".join(played.outcomes)).classes("text-xs opacity-60 q-px-md")


def _bubble(session: GameSession, speaker_id: EntityId | None, text: str, *, sent: bool) -> None:
    speaker = None if speaker_id is None else session.state.world.require(speaker_id)
    icon = None if speaker_id is None else session.icon(speaker_id)
    name = "DM" if speaker is None else speaker.name
    message = ui.chat_message(text, name=name, sent=sent).classes("w-full")
    if speaker is None:
        message.props("bg-color=grey-3")
    with message.add_slot("avatar"):
        _avatar(icon, None if speaker is None else name)


def _avatar(icon: Path | None, name: str | None) -> None:
    """`name` is None for the DM, whose avatar is the one shipped material icon."""
    with ui.avatar(color="grey-8", size="42px").classes("q-mx-sm"):
        if icon is not None:
            ui.image(icon)
        elif name is None:
            ui.icon(DM_ICON)
        else:
            ui.label(name[:1].upper()).classes("text-subtitle1")


def sheet_panel(session: GameSession) -> None:
    player = session.state.player
    _entity_row(session.icon(PLAYER_ID), player.name, player.brief)
    if player.traits:
        _heading("Traits")
        with ui.row().classes("w-full items-center").style("gap: 0.35rem"):
            for trait in player.traits:
                badge = ui.badge(trait.name).props("color=grey-8 outline")
                if trait.text:
                    badge.tooltip(trait.text)
    for label, value in session.engine.sheet_view(session.state):
        _labeled_value(label, value)
    inventory = player_scene(session.state).inventory
    if inventory:
        _heading("Carrying")
        for item in inventory:
            _entity_row(session.icon(item.id), item.name, item.brief)
    threads = thread_summaries(session.state)
    if threads:
        _heading("Threads")
        for thread in threads:
            _thread_card(thread)


def _labeled_value(label: str, value: str) -> None:
    with ui.row().classes("w-full items-baseline no-wrap mt-2").style("gap: 0.5rem"):
        ui.label(label).classes("text-xs font-bold opacity-60")
        ui.label(value or "—").classes("text-sm")


def _heading(title: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-4")


def _thread_card(thread: ThreadSummary) -> None:
    with ui.column().classes("w-full mt-2").style("gap: 0"):
        ui.label(thread.title).classes("text-sm font-bold")
        parts = (thread.status, thread.stage or "", thread.clock)
        ui.label(" · ".join(part for part in parts if part)).classes("text-xs opacity-60")


def journal_panel(session: GameSession) -> None:
    view = JournalView.of(session.state)

    def export() -> None:
        ui.notify(f"Journal written to {session.export_journal()}")

    ui.button("Export markdown", icon="download", on_click=export).props("flat dense")
    if view.threads:
        _heading("Threads")
        for thread in view.threads:
            _thread_card(thread)
    if view.memories:
        _heading("What is remembered")
        for memory in view.memories:
            ui.label(f"- {memory}").classes("text-sm whitespace-pre-wrap")
    scene = player_scene(session.state)
    if scene.known_elsewhere:
        _heading("What you know of")
        for entity in scene.known_elsewhere:
            _entity_row(
                session.icon(entity.id), entity.name, scene.placement_of(entity) or entity.brief
            )
    _heading("Chronicle")
    for number, exchange in reversed(list(enumerate(view.chronicle, start=1))):
        with ui.expansion(f"turn {number}: {exchange.prompt}").classes("w-full"):
            for line in exchange.lines:
                ui.markdown(attributed_line(session.state, line)).classes("text-sm")


def role_badges(session: GameSession) -> None:
    with ui.row().classes("items-center").style("gap: 0.25rem"):
        for role in session.role_names:
            colour = "primary" if session.step == role else "grey-7"
            ui.badge(role).props(f"color={colour}")


def trace_panel(session: GameSession) -> None:
    entries = session.entries
    if not entries:
        ui.label("No turns yet this session.").classes("opacity-60")
    turns = 0
    titles: list[str] = []
    for entry in entries:
        match entry:
            case Turn(prompt=prompt):
                turns += 1
                titles.append(f"turn {turns}: {prompt}")
            case Applied(entry=entry_kind):
                titles.append(f"after turn {turns}: {entry_kind}")
    for index, entry in reversed(list(enumerate(entries))):
        with ui.expansion(titles[index], value=index == len(entries) - 1):
            _entry_trace(entry)


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


def _entry_trace(entry: TraceEntry) -> None:
    match entry:
        case Applied(entry=entry_kind, facts=facts):
            _section(entry_kind.upper(), _facts(facts))
        case Turn():
            _turn_trace(entry)


def _turn_trace(turn: Turn) -> None:
    for step in turn.steps:
        _section(step.name.upper(), _output(step))
    _section("FACTS (private)", _facts(turn.facts))
    shown = [step for step in turn.steps if step.prompt is not None]
    if shown:
        with ui.expansion("what each role was shown").classes("w-full mt-3"):
            for step in shown:
                _section(step.name.upper(), step.prompt or "")


def _output(step: StepTrace) -> str:
    match step.output:
        case None:
            return "- (nothing)"
        case str() as text:
            return text
        case body:
            return json.dumps(body, indent=2)


def _facts(facts: Sequence[Fact]) -> str:
    lines = [f"- {fact.trace}" for fact in facts]
    return "\n".join(lines) or "- (none)"


def advancement_panel(session: GameSession, refresh: Callable[[], None]) -> None:
    """The one advancement panel; shown only when the engine plugs in a growth mechanic."""
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


def _summary(offer: Offer) -> None:
    ui.label(offer.prompt).classes("text-sm font-bold")
    if offer.text:
        ui.label(offer.text).classes("text-sm opacity-70 whitespace-pre-wrap")


def _intent_form(session: GameSession, offer: Offer, refresh: Callable[[], None]) -> None:
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
            session.drafted = Drafted(offer=offer, proposal=await session.propose(offer, intent))
        refresh()

    ui.button("Propose", on_click=propose).props("color=primary")


def _review(session: GameSession, drafted: Drafted, refresh: Callable[[], None]) -> None:
    ui.label("Proposed changes").classes("text-sm font-bold mt-3")
    try:
        lines = [f"- {fact.trace}" for fact in session.preview(drafted)]
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
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
