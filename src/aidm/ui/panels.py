"""The panels. The trace is the point of the app: it shows what every role saw and produced."""

from nicegui import ui

from ..domain.events import render
from ..domain.models import ROLES
from ..domain.turn import Turn
from .session import session


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


@ui.refreshable
def chat() -> None:
    if not session.state.history:
        ui.label(session.state.scenario.premise).classes("text-sm italic opacity-70")
    for exchange in session.state.history:
        ui.chat_message(exchange.prompt, name="You", sent=True)
        ui.chat_message(exchange.narration, name="DM")


@ui.refreshable
def role_badges() -> None:
    for role in ROLES:
        colour = "primary" if session.step == role else "grey-7"
        ui.badge(role).props(f"color={colour}")


@ui.refreshable
def state_panel() -> None:
    ui.code(session.state.model_dump_json(indent=2), language="json").classes("w-full text-xs")


@ui.refreshable
def trace_panel() -> None:
    if not session.turns:
        ui.label("No turns yet this session.").classes("opacity-60")
    for number, turn in reversed(list(enumerate(session.turns, 1))):
        with ui.expansion(f"turn {number}: {turn.prompt}", value=number == len(session.turns)):
            _turn_trace(turn)


def _turn_trace(turn: Turn) -> None:
    _section("DIRECTOR guidance (private)", turn.direction.guidance)
    _section("DIRECTOR tone (to the narrator)", turn.direction.tone)
    _section("ACTOR events", render(turn.events))
    _section("ACTOR report", turn.report)
    _section("NARRATOR", turn.narration)
    requests = "\n".join(f"- {r.kind} {r.name}: {r.brief}" for r in turn.growth.requests)
    _section("MAINTAINER", requests or "- (nothing new)")
    for entity in turn.created:
        detail = entity.detail.description if entity.detail else ""
        _section(f"CREATOR [{entity.kind}]", f"{entity.name} — {detail}")
    with ui.expansion("what each role was shown").classes("w-full mt-3"):
        for role, prompt in turn.prompts.items():
            _section(role.upper(), prompt)
