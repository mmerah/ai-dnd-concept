"""The trace panel: for each turn, what every role saw and produced. The point of the app."""

from collections.abc import Sequence

from nicegui import ui

from ...domain.models import Consequence, RejectedGrowth, Turn
from ...domain.reducer import render
from ..session import Session

# Branch/child fields are rendered by the recursive walk, not dumped inline as opaque dicts.
_NESTED_FIELDS = ("on_success", "on_failure", "then")

_REJECTION_TEXT = {"duplicate_name": "name already exists", "over_cap": "over the growth cap"}


def _section(title: str, body: str) -> None:
    ui.label(title).classes("text-xs font-bold opacity-60 mt-3")
    ui.label(body).classes("text-sm whitespace-pre-wrap")


@ui.refreshable
def trace_panel(session: Session) -> None:
    if not session.turns:
        ui.label("No turns yet this session.").classes("opacity-60")
    for number, turn in reversed(list(enumerate(session.turns, 1))):
        with ui.expansion(f"turn {number}: {turn.prompt}", value=number == len(session.turns)):
            _turn_trace(turn)


def _mechanics(mechanics: Sequence[Consequence]) -> str:
    """Render the consequence tree, indenting each branch/child under its parent."""

    def lines(items: Sequence[Consequence], depth: int) -> list[str]:
        out: list[str] = []
        for c in items:
            fields = c.model_dump(exclude={"action", *_NESTED_FIELDS})
            out.append(f"{'  ' * depth}{c.action} {fields}")
            for name in _NESTED_FIELDS:
                branch = getattr(c, name, None)
                if branch:
                    out.append(f"{'  ' * depth}  {name}:")
                    out += lines(branch, depth + 2)
        return out

    return "\n".join(lines(mechanics, 0)) or "(no mechanics)"


def _rejected(rejected: list[RejectedGrowth]) -> str:
    return "\n".join(
        f"- {r.request.kind} {r.request.name}: {_REJECTION_TEXT[r.reason]}" for r in rejected
    )


def _turn_trace(turn: Turn) -> None:
    _section("DIRECTOR intent (to the narrator)", turn.direction.intent)
    _section("DIRECTOR tone (to the narrator)", turn.direction.tone)
    _section("DIRECTOR mechanics (private)", _mechanics(turn.direction.mechanics))
    _section("EVENTS", render(turn.events))
    _section("NARRATOR", turn.narration)
    requests = "\n".join(f"- {r.kind} {r.name}: {r.brief}" for r in turn.growth.requests)
    _section("MAINTAINER", requests or "- (nothing new)")
    if turn.rejected:
        _section("MAINTAINER rejected", _rejected(turn.rejected))
    for entity in turn.created:
        detail = entity.detail.description if entity.detail else ""
        _section(f"CREATOR [{entity.kind}]", f"{entity.name} — {detail}")
    with ui.expansion("what each role was shown").classes("w-full mt-3"):
        for role, prompt in turn.prompts.items():
            _section(role.upper(), prompt)
