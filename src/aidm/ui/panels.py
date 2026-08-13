import json
from collections.abc import Callable, Sequence

from nicegui import ui

from aidm.app.session import AdvancementOffer, GameSession, ProposalBase
from aidm.state.facts import Fact
from aidm.state.turn import Advance, StepTrace, TraceEntry, Turn

from .busy import refuse_if_busy, working


def show_engine_badge(badge: tuple[str, str]) -> None:
    label, colour = badge
    ui.badge(label).props(f"color={colour} text-color=white").classes(
        "text-sm font-bold q-px-md q-py-sm"
    )


def chat(session: GameSession) -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    for exchange in session.state.history:
        ui.chat_message(exchange.prompt, name="You", sent=True)
        ui.chat_message(exchange.narration, name="DM")


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
            case Advance():
                titles.append(f"after turn {turns}: advancement")
    for index, entry in reversed(list(enumerate(entries))):
        with ui.expansion(titles[index], value=index == len(entries) - 1):
            _entry_trace(entry)


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


def _entry_trace(entry: TraceEntry) -> None:
    match entry:
        case Advance(facts=facts):
            _section("ADVANCEMENT", _facts(facts))
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
    """One panel for every engine; nothing is committed until the player confirms the draft."""
    offer = session.offer()
    if offer is None:
        ui.label("No advancement is on offer.").classes("opacity-70")
        return
    _summary(session, offer)
    if session.drafted is None:
        _intent_form(session, refresh)
    else:
        _review(session, session.drafted, refresh)


def _summary(session: GameSession, offer: AdvancementOffer) -> None:
    ui.label(f"{session.state.player.name} — advancement ready").classes("text-sm font-bold")
    ui.label(offer.prompt).classes("text-sm")
    if offer.text:
        ui.label(offer.text).classes("text-sm opacity-70 whitespace-pre-wrap")


def _intent_form(session: GameSession, refresh: Callable[[], None]) -> None:
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
            session.drafted = await session.propose(intent)
        refresh()

    ui.button("Propose", on_click=propose).props("color=primary")


def _review(session: GameSession, drafted: ProposalBase, refresh: Callable[[], None]) -> None:
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
        ui.button("Confirm advancement", on_click=confirm).props("color=primary")


def state_panel(session: GameSession) -> None:
    ui.code(
        session.state.model_dump_json(indent=2),
        language="json",
    ).classes("w-full text-xs")
