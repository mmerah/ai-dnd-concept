from collections.abc import Sequence

from aidm.domain.events import RuleEvent
from aidm.domain.growth import RejectedGrowth
from aidm.domain.presentation import trace_core_event
from aidm.domain.turn import Turn
from nicegui import ui

from ..session_model import Session

REJECTION_TEXT = {
    "duplicate_name": "name already exists",
    "over_cap": "over the growth cap",
}


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


def trace_panel(session: Session) -> None:
    if not session.app.turns:
        ui.label("No turns yet this session.").classes("opacity-60")
    numbered = list(enumerate(session.app.turns, 1))
    for number, turn in reversed(numbered):
        with ui.expansion(
            f"turn {number}: {turn.prompt}",
            value=number == len(session.app.turns),
        ):
            _turn_trace(session, turn)


def _turn_trace(session: Session, turn: Turn) -> None:
    presentation = session.app.engine.presentation
    _section("DIRECTOR intent (to the narrator)", turn.direction.intent)
    _section("DIRECTOR tone (to the narrator)", turn.direction.tone)
    _section(
        "DIRECTOR mechanics (private)",
        presentation.trace_direction(turn.direction),
    )
    private = [
        (
            presentation.trace_event(event)
            if isinstance(event, RuleEvent)
            else trace_core_event(event)
        )
        for event in turn.events
    ]
    _section("EVENTS (private)", "\n".join(f"- {line}" for line in private) or "- (none)")
    _section("NARRATOR-SAFE EVIDENCE", turn.narrator_evidence or "- (none)")
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


def _rejected(rejected: Sequence[RejectedGrowth]) -> str:
    return "\n".join(
        f"- {item.request.kind} {item.request.name}: {REJECTION_TEXT[item.reason]}"
        for item in rejected
    )
