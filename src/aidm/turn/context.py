from collections.abc import Sequence
from functools import cache
from pathlib import Path

from aidm.core.io import ENCODING
from aidm.core.model import AnyGame
from aidm.core.play import Narration, PendingDecision, SceneRecord
from aidm.core.tools import schema_text
from aidm.core.views import NarratorView, lines_of, render_history, sections, told_narration

ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def render_master(
    instructions: str,
    engine_sections: Sequence[tuple[str, str]],
    state: AnyGame,
    scenes: Sequence[SceneRecord],
    action: str,
    *,
    notes: Sequence[str] = (),
) -> str:
    """The whole spawn prompt: every spawn is cold, so the picture rides in it."""
    return sections(
        (
            ("YOUR ROLE", _prompt("master")),
            ("THE RULES OF THIS GAME", instructions),
            ("SCENARIO", f"{state.scenario.title}\n{state.scenario.premise}"),
            (f"RECENT PLAY (this is turn {state.turn + 1})", render_history(scenes)),
            *engine_sections,
            ("NOTES FROM THE RULES", lines_of(f"- {note}" for note in notes)),
            ("WAITING ON THE PLAYER", _waiting(state.pending)),
            ("PLAYER ACTION", action),
        )
    )


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[SceneRecord]
) -> str:
    """Only the narrator view reaches this, so hidden canon has no path into the prose."""
    return sections(
        (
            ("YOUR ROLE", _prompt("narrator")),
            ("WHAT THE PLAYER HAS READ", "\n\n".join(told_narration(scenes)) or "(nothing yet)"),
            ("SCENE", f"{view.title}\n{view.situation}"),
            ("WHAT THIS SCENE IS ABOUT", view.focus),
            (
                "WHO IS HERE",
                lines_of(f"- {subject.name} — {subject.brief}" for subject in view.subjects),
            ),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


@cache
def _prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding=ENCODING)


def _waiting(pending: PendingDecision | None) -> str:
    if pending is None:
        return "- (nothing; the turn is yours to run)"
    lines = [
        f"- {option.id}: {option.label} {option.detail}".rstrip() for option in pending.options
    ]
    lines.append(
        "- (the player answers in their own words)"
        if pending.allows_text
        else "- (choose one option above)"
    )
    return "\n".join([f"{pending.kind}: {pending.prompt}", *lines])
