from collections.abc import Sequence
from functools import cache
from pathlib import Path

from aidm.core.io import ENCODING
from aidm.core.model import AnyGame
from aidm.core.play import Interjection, Narration, SceneRecord
from aidm.core.tools import schema_text
from aidm.core.views import (
    NarratorView,
    Rows,
    Sections,
    Subject,
    lines_of,
    render_history,
    sections,
    told_history,
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def render_master(
    instructions: str,
    engine_sections: Sequence[tuple[str, str]],
    state: AnyGame,
    scenes: Sequence[SceneRecord],
    action: str,
    *,
    played: int,
    notes: Sequence[str] = (),
) -> str:
    return sections(
        (
            ("YOUR ROLE", _prompt("master")),
            ("THE RULES OF THIS GAME", instructions),
            ("SCENARIO", f"{state.scenario.title}\n{state.scenario.premise}"),
            ("THE SCOPE OF PLAY", state.scenario.scope),
            (f"RECENT PLAY (this is turn {played + 1})", render_history(scenes)),
            *engine_sections,
            ("NOTES FROM THE RULES", lines_of(f"- {note}" for note in notes)),
            ("PLAYER ACTION", action),
        )
    )


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[SceneRecord]
) -> str:
    return sections(
        (
            ("YOUR ROLE", _prompt("narrator")),
            *_picture(view, scenes, evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


def render_interjection(
    view: NarratorView,
    member: Subject,
    sheet: Rows,
    scenes: Sequence[SceneRecord],
    evidence: str,
) -> str:
    role = _prompt("interjection").format(name=member.name, brief=member.brief, id=member.id)
    return sections(
        (
            ("YOUR ROLE", role),
            (
                "YOUR SHEET",
                "\n".join(f"- {label}: {value}" for label, value in sheet) or "(none)",
            ),
            *_picture(view, scenes, evidence, reader=member),
            ("ANSWER WITH", schema_text(Interjection)),
        )
    )


def _picture(
    view: NarratorView,
    scenes: Sequence[SceneRecord],
    evidence: str,
    *,
    reader: Subject | None = None,
) -> Sections:
    """`reader` is who reads it: nobody (the player themself) or a member reading about them."""
    lead, beside = ("you are", "with you") if reader is None else ("the player is", "with them")
    subjects = {subject.id: subject for subject in view.subjects}
    first, *rest = (subjects[member_id] for member_id in view.party)
    members = [f"{beside}: {member.name} — {member.brief}" for member in rest]
    party = "\n".join(
        (f"{lead} {first.name} — {first.brief}", *(members or [f"nobody travels {beside}"]))
    )
    others = view.others()
    who_is_here = (
        lines_of(f"- {subject.name} — {subject.brief}" for subject in others)
        if others
        else "(nobody else)"
    )
    return (
        ("WHAT THE PLAYER HAS READ", told_history(scenes)),
        ("SCENE", f"{view.title}\n{view.situation}"),
        *((("WHAT THIS SCENE IS ABOUT", view.focus),) if view.focus else ()),
        ("WHO IS HERE", who_is_here),
        ("YOUR PARTY", party),
        ("THE PLAYER'S SHEET", lines_of(f"- {label}: {value}" for label, value in view.sheet)),
        ("WHAT HAPPENED", evidence),
    )


@cache
def _prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding=ENCODING)
