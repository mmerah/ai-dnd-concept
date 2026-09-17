import logging
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from pydantic import BaseModel

from aidm.app.spawn import Spawner
from aidm.config import Role
from aidm.core.entities import Refusal
from aidm.core.facts import Fact, traced
from aidm.core.io import parse_text, read_cached_text
from aidm.core.model import AnyGame, Check, WorldsmithAnswer
from aidm.core.play import Chapter, Interjection, Narration, SpokenLine
from aidm.core.prompt import Sections, lines_of, recent_history, section_if, sections
from aidm.core.tools import schema_text
from aidm.core.views import Companion, NarratorView, Subject
from aidm.engines.seam import AnyEngine
from aidm.turn.run import Turn

LOGGER = logging.getLogger(__name__)

RETRIES = 1
PROMPTS_DIR = Path(__file__).parent / "prompts"
PAUSED = (
    'play pauses here on the player\'s decision: "{prompt}" End on the pause; settle nothing they '
    "have not yet answered."
)
REQUESTED = (
    "play stops here while the world is written on; end on this moment and settle nothing "
    "beyond what happened."
)
OPENING_NARRATION = (
    "The story begins here; the player has read nothing yet. Tell them, in the fiction and in "
    "this order: who they are (YOUR PARTY names them first) and where they stand; what is in "
    "front of them, the situation as they see it now; what they are here to do, from WHAT THIS "
    "SCENE IS ABOUT where it is given, said as the thing pulling at them; and two or three "
    "things they could plainly do first, offered by the place and the people, in prose, never "
    "as a list. Six to eight sentences. They have not acted, so settle nothing."
)


async def master(spawner: Spawner, turn: Turn) -> None:
    """A crashed game master still played the turn, if it applied anything legal first."""
    try:
        await spawner.run("master", turn.picture(), None, turn)
    except Refusal as failed:
        if not turn.landed():
            raise
        LOGGER.warning(
            "the game master failed after applying %d facts: %s", len(turn.facts), failed
        )


async def narrate(
    spawner: Spawner, engine: AnyEngine, draft: AnyGame, facts: tuple[Fact, ...], prompt: str
) -> tuple[SpokenLine, ...]:
    view = engine.narrator_view(draft)
    evidence = traced(facts, told_only=True)
    if (pending := draft.pending) is not None:
        evidence += f"\n- {PAUSED.format(prompt=pending.prompt)}"
    if draft.generation is not None:
        evidence += f"\n- {REQUESTED}"
    narration = await ask(
        spawner,
        "narrator",
        render_narrator(view, evidence=evidence, prompt=prompt, scenes=draft.log),
        Narration,
        view.check_narration,
    )
    return view.spoken(narration.lines)


async def interject(
    spawner: Spawner, engine: AnyEngine, state: AnyGame, member: Companion
) -> tuple[tuple[SpokenLine, ...], str]:
    view = engine.narrator_view(state)
    history = state.exchanges()
    evidence = traced(history[-1].facts if history else (), told_only=True)
    answer = await ask(
        spawner,
        "narrator",
        render_interjection(view, member, state.log, evidence),
        Interjection,
        partial(view.check_interjection, member.id),
    )
    return view.spoken(answer.lines), answer.proposal


async def ask[T: BaseModel](
    spawner: Spawner, role: Role, prompt: str, model: type[T], check: Check[T]
) -> T:
    asked, refused, session = prompt, "", None
    for _ in range(RETRIES + 1):
        try:
            spoken = await spawner.run(role, asked, session)
            session = spoken.session
            answer = parse_text(model, spoken.text)
            check(answer)
        except Refusal as invalid:
            refused = str(invalid)
        else:
            return answer
        correction = f"Your last answer was refused: {refused}\nAnswer again, fixed."
        # The retry carries on the refused attempt, which has read the prompt already.
        asked = correction if session is not None else f"{prompt}\n\n{correction}"
    LOGGER.warning("the %s answered nothing usable: %s", role, refused)
    raise Refusal(f"the {role} answered nothing usable")


def worldsmith(spawner: Spawner) -> WorldsmithAnswer:
    return partial(ask, spawner, "worldsmith")


def render_narrator(
    view: NarratorView, *, evidence: str, prompt: str, scenes: Sequence[Chapter]
) -> str:
    return sections(
        (
            ("YOUR ROLE", read_cached_text(PROMPTS_DIR / "narrator.md")),
            *_picture(view, scenes, evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", schema_text(Narration)),
        )
    )


def render_interjection(
    view: NarratorView, member: Companion, scenes: Sequence[Chapter], evidence: str
) -> str:
    role = read_cached_text(PROMPTS_DIR / "interjection.md").format(
        name=member.label, brief=member.detail, id=member.id
    )
    return sections(
        (
            ("YOUR ROLE", role),
            (
                "YOUR SHEET",
                "\n".join(f"- {label}: {value}" for label, value in member.sheet) or "(none)",
            ),
            *_picture(view, scenes, evidence, reader=member),
            ("ANSWER WITH", schema_text(Interjection)),
        )
    )


def _picture(
    view: NarratorView,
    scenes: Sequence[Chapter],
    evidence: str,
    *,
    reader: Subject | None = None,
) -> Sections:
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
        ("WHAT THE PLAYER HAS READ", recent_history(scenes)),
        ("SCENE", f"{view.title}\n{view.situation}"),
        *section_if("WHAT THIS SCENE IS ABOUT", view.focus),
        ("WHO IS HERE", who_is_here),
        ("YOUR PARTY", party),
        ("THE PLAYER'S SHEET", lines_of(f"- {label}: {value}" for label, value in view.sheet)),
        ("WHAT HAPPENED", evidence),
    )
