from collections.abc import Sequence
from pathlib import Path

from aidm.core.io import read_prompt
from aidm.core.play import Interjection, Narration, SceneRecord
from aidm.core.prompt import lines_of, sections, told_history
from aidm.core.tools import schema_text
from aidm.core.views import NarratorView, Pairs, Subject

PROMPTS_DIR = Path(__file__).parent / "prompts"


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[SceneRecord]
) -> str:
    return sections(
        (
            ("YOUR ROLE", read_prompt(PROMPTS_DIR / "narrator.md")),
            *_picture(view, scenes, evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


def render_interjection(
    view: NarratorView,
    member: Subject,
    sheet: Pairs,
    scenes: Sequence[SceneRecord],
    evidence: str,
) -> str:
    role = read_prompt(PROMPTS_DIR / "interjection.md").format(
        name=member.label, brief=member.detail, id=member.id
    )
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
) -> Pairs:
    """`reader` is who reads it: nobody (the player themself) or a member reading about them."""
    lead, beside = ("you are", "with you") if reader is None else ("the player is", "with them")
    subjects = {subject.id: subject for subject in view.subjects}
    first, *rest = (subjects[member_id] for member_id in view.party)
    members = [f"{beside}: {member.headline}" for member in rest]
    party = "\n".join((f"{lead} {first.headline}", *(members or [f"nobody travels {beside}"])))
    others = view.others()
    who_is_here = (
        lines_of(f"- {subject.headline}" for subject in others) if others else "(nobody else)"
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
