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
from aidm.core.prompt import (
    Sections,
    lines_of,
    recent_history,
    render_history,
    section_if,
    sections,
)
from aidm.core.tools import schema_text
from aidm.core.views import Companion, NarratorView, Subject
from aidm.engines.engine import AnyEngine
from aidm.turn import Turn

LOGGER = logging.getLogger(__name__)

RETRIES = 1
PROMPTS_DIR = Path(__file__).parent / "prompts"
MASTER_ROLE = PROMPTS_DIR / "master.md"
PAUSED = (
    'play pauses here on the player\'s decision: "{prompt}" End at the pause. Settle nothing that '
    "the player has not answered."
)
REQUESTED = (
    "play stops here while the world grows. End at this moment. Settle nothing more than what "
    "happened."
)
OPENING_NARRATION = (
    "The story starts here. The player has read nothing yet. Tell the player four things, in the "
    "story and in this order. First, who the player is (YOUR PARTY gives the name first) and "
    "where the player stands. Second, what is in front of the player, the situation as the player "
    "sees it now. Third, what the player is here to do. Take it from WHAT THIS SCENE IS ABOUT "
    "when that section is given. Say it as the thing that pulls at the player. Fourth, two or "
    "three things that the player can do first, offered by the place and the people. Write all of "
    "it in prose, never as a list. Write six to eight sentences. The player has not acted, so "
    "settle nothing."
)


async def run_master(spawner: Spawner, turn: Turn) -> None:
    """A failed game master still played the turn when facts landed first."""
    prompt = render_master(
        turn.engine.instructions,
        turn.engine.master_sections(turn.draft),
        turn.draft,
        turn.player_action,
        notes=turn.notes,
    )
    try:
        await spawner.run("master", prompt, None, turn)
    except Refusal as failed:
        if not turn.landed:
            raise
        LOGGER.warning(
            "the game master failed after applying %d facts: %s", len(turn.facts), failed
        )


async def run_narrator(
    spawner: Spawner, engine: AnyEngine, draft: AnyGame, facts: tuple[Fact, ...], prompt: str
) -> tuple[SpokenLine, ...]:
    view = engine.narrator_view(draft)
    evidence = traced(facts, told_only=True)
    if (pending := draft.pending) is not None:
        evidence += f"\n- {PAUSED.format(prompt=pending.prompt)}"
    if draft.commission is not None:
        evidence += f"\n- {REQUESTED}"
    narration = await ask(
        spawner,
        "narrator",
        render_narrator(view, evidence=evidence, prompt=prompt, scenes=draft.log),
        Narration,
        view.check_narration,
    )
    return view.spoken(narration.lines)


async def run_interjection(
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
    asked, refused, conversation = prompt, "", None
    for _ in range(RETRIES + 1):
        try:
            spoken = await spawner.run(role, asked, conversation)
            conversation = spoken.conversation
            answer = parse_text(model, spoken.text)
            check(answer)
        except Refusal as invalid:
            refused = str(invalid)
        else:
            return answer
        correction = f"Your last answer was refused: {refused}\nAnswer again. Correct the error."
        # The retry continues the refused attempt, which has read the prompt already.
        asked = correction if conversation is not None else f"{prompt}\n\n{correction}"
    LOGGER.warning("the %s answered nothing usable: %s", role, refused)
    raise Refusal(f"the {role} answered nothing usable")


def worldsmith_answer(spawner: Spawner) -> WorldsmithAnswer:
    return partial(ask, spawner, "worldsmith")


# The worldsmith's renderer stays in engines/: it needs the engine's own sections.
def render_master(
    instructions: str,
    engine_sections: Sections,
    state: AnyGame,
    action: str,
    *,
    notes: Sequence[str] = (),
) -> str:
    played = sum(len(chapter.exchanges) for chapter in state.log)
    return sections(
        (
            ("YOUR ROLE", read_cached_text(MASTER_ROLE)),
            ("THE RULES OF THIS GAME", instructions),
            ("SCENARIO", f"{state.scenario.title}\n{state.scenario.premise}"),
            ("THE SCOPE OF PLAY", state.scenario.scope),
            (f"RECENT PLAY (this is turn {played + 1})", render_history(state.log)),
            *engine_sections,
            ("NOTES FROM THE RULES", lines_of(f"- {note}" for note in notes)),
            ("PLAYER ACTION", action),
        )
    )


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
        name=member.name, brief=member.brief, id=member.id
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
