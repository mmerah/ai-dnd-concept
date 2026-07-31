from collections.abc import Sequence

from nicegui import ui

from aidm.engine import Engine, trace_direction, trace_fact
from aidm.growth import RejectedGrowth
from aidm.transition import Fact
from aidm.turn import Advance, TraceEntry, Turn

from ..session import Session

REJECTION_TEXT = {
    "duplicate_name": "name already exists",
    "over_cap": "over the growth cap",
}


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


def trace_panel(session: Session) -> None:
    entries = session.app.entries
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
            _entry_trace(session.app.engine, entry)


def _entry_trace(engine: Engine, entry: TraceEntry) -> None:
    match entry:
        case Advance(facts=facts):
            _section("ADVANCEMENT", _facts(engine, facts))
        case Turn():
            _turn_trace(engine, entry)


def _turn_trace(engine: Engine, turn: Turn) -> None:
    _section("DIRECTOR intent (to the narrator)", turn.direction.intent)
    _section("DIRECTOR tone (to the narrator)", turn.direction.tone)
    _section("DIRECTOR mechanics (private)", trace_direction(engine, turn.direction))
    _section("FACTS (private)", _facts(engine, turn.facts))
    _section("NARRATOR-SAFE EVIDENCE", turn.narrator_evidence)
    _section("NARRATOR", turn.narration)
    requests = "\n".join(
        f"- {request.kind} {request.name}: {request.brief}" for request in turn.growth.requests
    )
    _section("MAINTAINER", requests or "- (nothing new)")
    if turn.rejected:
        _section("MAINTAINER rejected", _rejected(turn.rejected))
    for entity in turn.created:
        detail = entity.detail.description if entity.detail else ""
        _section(f"CREATOR [{entity.kind}]", f"{entity.name} — {detail}")
    with ui.expansion("what each role was shown").classes("w-full mt-3"):
        for role, prompt in turn.prompts.items():
            _section(role.upper(), prompt)


def _facts(engine: Engine, facts: Sequence[Fact]) -> str:
    lines = [f"- {trace_fact(engine, fact)}" for fact in facts]
    return "\n".join(lines) or "- (none)"


def _rejected(rejected: Sequence[RejectedGrowth]) -> str:
    return "\n".join(
        f"- {item.request.kind} {item.request.name}: {REJECTION_TEXT[item.reason]}"
        for item in rejected
    )
