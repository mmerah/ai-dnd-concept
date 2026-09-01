import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.core.io import engine_text
from aidm.core.model import AnyGame, ScenarioMeta
from aidm.core.play import Exchange, Narration, PendingDecision
from aidm.core.tools import schema_of
from aidm.core.views import NarratorView
from aidm.core.views import sections as render_sections

ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

MASTER = engine_text(_PROMPTS_DIR / "master.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")


def render_master(instructions: str, action: str) -> str:
    """The spawn prompt: the rules, and the action. `start_turn` hands back the picture."""
    return render_sections(
        (
            ("YOUR ROLE", MASTER),
            ("THE RULES OF THIS GAME", instructions),
            ("PLAYER ACTION", action),
        )
    )


def render_picture(
    sections: Sequence[tuple[str, str]],
    state: AnyGame,
    history: Sequence[Exchange],
    prompt: str,
    *,
    resumed: str = "",
    notes: Sequence[str] = (),
    recent: int = 0,
) -> str:
    """What `start_turn` and `scene` hand back; the engine states every section of the world."""
    ending = (
        (
            ("THE PLAYER'S DECISION, ALREADY RESOLVED", resumed),
            ("PLAYER ACTION", ANSWERED_BY_OPTION),
        )
        if resumed
        else (("PLAYER ACTION", prompt),)
    )
    return render_sections(
        (
            _premise(state.scenario),
            (f"RECENT PLAY (this is turn {state.turn + 1})", _recent(history, recent)),
            *sections,
            ("NOTES FROM THE RULES", "\n".join(f"- {note}" for note in notes) or "- (none)"),
            ("WAITING ON THE PLAYER", _waiting(state.pending)),
            *ending,
        )
    )


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, passages: Sequence[str] = ()
) -> str:
    """Only the narrator view reaches this, so hidden canon has no path into the prose."""
    return render_sections(
        (
            ("YOUR ROLE", NARRATOR),
            ("WHAT THE PLAYER HAS READ", "\n\n".join(passages) or "(nothing yet)"),
            ("SCENE", f"{view.title}\n{view.situation}"),
            ("WHAT THIS SCENE IS ABOUT", view.focus),
            (
                "WHO IS HERE",
                "\n".join(f"- {one.name} — {one.brief}" for one in view.subjects) or "- (none)",
            ),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", _shape(Narration)),
        )
    )


def told_passages(history: Sequence[Exchange], limit: int) -> tuple[str, ...]:
    """What the player has already read, so continuity costs the narrator no hidden canon."""
    return tuple(one.narration for one in history[-limit:] if one.narration)


def _shape(model: type[BaseModel]) -> str:
    return json.dumps(schema_of(model), indent=2, ensure_ascii=False)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def _recent(history: Sequence[Exchange], limit: int) -> str:
    told = [_recent_exchange(one) for one in history]
    return "\n\n".join(told[-limit:]) or "(the game has not started yet)"


def _recent_exchange(exchange: Exchange) -> str:
    location = f"[at {exchange.where}] " if exchange.where else ""
    return f"> {exchange.prompt}\n{location}{exchange.narration}"


def _waiting(pending: PendingDecision | None) -> str:
    if pending is None:
        return "- (nothing; the turn is yours to run)"
    lines = [f"- {one.id}: {one.label} {one.detail}".rstrip() for one in pending.options]
    lines.append(
        "- (the player answers in their own words)"
        if pending.allows_text
        else "- (choose one option above)"
    )
    return "\n".join([f"{pending.kind}: {pending.prompt}", *lines])
