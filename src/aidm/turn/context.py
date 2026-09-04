from collections.abc import Sequence
from functools import cache
from pathlib import Path

from aidm.core.io import ENCODING
from aidm.core.model import AnyGame
from aidm.core.play import HistoryRecord, Narration
from aidm.core.tools import schema_text
from aidm.core.views import NarratorView, lines_of, render_history, sections, told_narration

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def render_master(
    instructions: str,
    engine_sections: Sequence[tuple[str, str]],
    state: AnyGame,
    scenes: Sequence[HistoryRecord],
    action: str,
    *,
    played: int,
    notes: Sequence[str] = (),
) -> str:
    """The whole spawn prompt: every spawn is cold, so the picture rides in it."""
    return sections(
        (
            ("YOUR ROLE", _prompt("master")),
            ("THE RULES OF THIS GAME", instructions),
            ("SCENARIO", f"{state.scenario.title}\n{state.scenario.premise}"),
            (f"RECENT PLAY (this is turn {played + 1})", render_history(scenes)),
            *engine_sections,
            ("NOTES FROM THE RULES", lines_of(f"- {note}" for note in notes)),
            ("PLAYER ACTION", action),
        )
    )


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[HistoryRecord]
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
            ("THE PLAYER'S SHEET", lines_of(f"- {label}: {value}" for label, value in view.sheet)),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


@cache
def _prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding=ENCODING)
