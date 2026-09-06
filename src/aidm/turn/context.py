from collections.abc import Sequence
from functools import cache
from pathlib import Path

from aidm.core.io import ENCODING
from aidm.core.model import AnyGame
from aidm.core.play import Interjection, Narration, SceneRecord
from aidm.core.tools import schema_text
from aidm.core.views import (
    NarratorView,
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
    """The whole spawn prompt: every spawn is cold, so the picture rides in it."""
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
    """Only the narrator view reaches this, so hidden canon has no path into the prose."""
    return sections(
        (
            ("YOUR ROLE", _prompt("narrator")),
            *_picture(view, scenes, evidence, party=_party_lines(view)),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


def render_interjection(
    view: NarratorView, member: Subject, scenes: Sequence[SceneRecord], evidence: str
) -> str:
    """The member reads the narrator's whole picture: the view holds nothing hidden."""
    role = _prompt("interjection").format(name=member.name, brief=member.brief, id=member.id)
    party = _party_lines(view, lead="the player is", beside="with them")
    return sections(
        (
            ("YOUR ROLE", role),
            *_picture(view, scenes, evidence, party=party),
            ("ANSWER WITH", schema_text(Interjection)),
        )
    )


def _picture(
    view: NarratorView, scenes: Sequence[SceneRecord], evidence: str, *, party: str
) -> Sections:
    return (
        ("WHAT THE PLAYER HAS READ", told_history(scenes)),
        ("SCENE", f"{view.title}\n{view.situation}"),
        *((("WHAT THIS SCENE IS ABOUT", view.focus),) if view.focus else ()),
        ("WHO IS HERE", _who_is_here(view)),
        ("YOUR PARTY", party),
        ("THE PLAYER'S SHEET", lines_of(f"- {label}: {value}" for label, value in view.sheet)),
        ("WHAT HAPPENED", evidence),
    )


def _who_is_here(view: NarratorView) -> str:
    others = view.others()
    return (
        lines_of(f"- {subject.name} — {subject.brief}" for subject in others)
        if others
        else "(nobody else)"
    )


def _party_lines(view: NarratorView, *, lead: str = "you are", beside: str = "with you") -> str:
    """`lead` and `beside` say who reads it: the player, or a member reading about them."""
    subjects = {subject.id: subject for subject in view.subjects}
    first, *rest = (subjects[member_id] for member_id in view.party)
    members = [f"{beside}: {member.name} — {member.brief}" for member in rest]
    return "\n".join(
        (f"{lead} {first.name} — {first.brief}", *(members or [f"nobody travels {beside}"]))
    )


@cache
def _prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding=ENCODING)
