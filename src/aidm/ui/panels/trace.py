import json
from collections.abc import Sequence

from nicegui import ui

from aidm.app.session import GameSession
from aidm.state.facts import Fact
from aidm.state.turn import Advance, StepTrace, TraceEntry, Turn


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


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
