import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.core.io import engine_text
from aidm.core.model import Game, ScenarioMeta, SceneWrite
from aidm.core.play import Narration, PendingDecision
from aidm.core.tools import schema_of
from aidm.core.views import NarratorView
from aidm.kits.scenes.render import SheetRows, entity_line, thread_lines
from aidm.kits.scenes.state import SceneRun, SceneState

ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)
# Stands where the player's action goes; `pursuit` is what they said they were leaving for.
CROSSING = (
    "The player is leaving WHAT THE PLAYER HAS READ for the place in SCENE. They asked for this: "
    '"{pursuit}"\n\n'
    "Write the crossing: a sentence of leaving, then the arrival. Cover the distance and the time "
    "in the fewest words that make it real, and end on what they see first. WHAT HAPPENED names "
    "anyone who travelled with them. They have not acted in the new place yet, so settle nothing."
)
SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
)

# Its ending is what the next scene follows; the whole of it would grow with the game forever.
TAIL_EXCHANGES = 3

_PROMPTS_DIR = Path(__file__).parent / "prompts"

MASTER = engine_text(_PROMPTS_DIR / "master.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")
WORLDSMITH = engine_text(_PROMPTS_DIR / "worldsmith.md")


def render_master(instructions: str, action: str) -> str:
    """The spawn prompt: the rules, and the action. `start_turn` hands back the picture."""
    return _sections(
        (
            ("YOUR ROLE", MASTER),
            ("THE RULES OF THIS GAME", instructions),
            ("PLAYER ACTION", action),
        )
    )


def render_picture(
    sections: Sequence[tuple[str, str]],
    state: Game,
    prompt: str,
    *,
    resumed: str = "",
    notes: Sequence[str] = (),
    recent: int = 0,
) -> str:
    """What `start_turn` and `scene` hand back; the engine states every section of the world."""
    # A chosen option is already applied: shown as its own words, a model settles it twice.
    ending = (
        (
            ("THE PLAYER'S DECISION, ALREADY RESOLVED", resumed),
            ("PLAYER ACTION", ANSWERED_BY_OPTION),
        )
        if resumed
        else (("PLAYER ACTION", prompt),)
    )
    return _sections(
        (
            _premise(state.scenario),
            (f"RECENT PLAY (this is turn {state.turn + 1})", _recent(state, recent)),
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
    return _sections(
        (
            ("YOUR ROLE", NARRATOR),
            ("WHAT THE PLAYER HAS READ", "\n\n".join(passages) or "(nothing yet)"),
            ("SCENE", f"{view.title}\n{view.situation}"),
            ("WHAT THIS SCENE IS ABOUT", view.question),
            (
                "WHO IS HERE",
                "\n".join(f"- {one.name} — {one.brief}" for one in view.subjects) or "- (none)",
            ),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
            ("ANSWER WITH", _shape(Narration)),
        )
    )


def render_worldsmith[S: BaseModel](
    world: SceneState[S], intent: str, guidance: str, rows: SheetRows
) -> str:
    """The whole material for one scene, assembled by code so no role has to remember it."""
    return _worldsmith(
        source=world.source,
        history=_history(world),
        cast="\n".join(entity_line(world, one, rows, where=True) for one in world.cast.values()),
        threads=thread_lines(world.threads.values(), standing_only=False),
        guidance=guidance,
        intent=intent,
    )


def render_opening(source: str, guidance: str) -> str:
    return _worldsmith(
        source=source,
        history="(no scenes yet — write the opening)",
        cast="(no cast yet — write the people and things this scene needs)",
        threads="- (none yet — open the first)",
        guidance=guidance,
        intent=(
            "Write the opening scene of this adventure: where the player starts, who is there, "
            "and what is waiting to be found."
        ),
    )


def told_passages(state: Game, limit: int) -> tuple[str, ...]:
    """What the player has already read, so continuity costs the narrator no hidden canon."""
    return tuple(one.narration for one in state.world.exchanges()[-limit:] if one.narration)


def _worldsmith(
    *,
    source: str,
    history: str,
    cast: str,
    threads: str,
    guidance: str,
    intent: str,
) -> str:
    return _sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none — write from the threads and the cast)"),
            ("SCENES SO FAR", history),
            ("THE WHOLE CAST", cast),
            ("THREADS", threads),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", _shape(SceneWrite)),
        )
    )


def _history[S: BaseModel](world: SceneState[S]) -> str:
    """A scene authored is not a scene played, and the next one has to follow from the second."""
    return "\n\n".join(
        "\n".join(
            (
                f"SCENE {number}: {run.scene.title} ({run.scene.place})",
                f"the question: {run.scene.question}",
                run.scene.situation,
                # Its end, not its whole play: the prompt must not grow with the game forever.
                "what happened: " + (_told(run) or "(nothing yet)"),
            )
        )
        for number, run in enumerate(world.runs, start=1)
    )


def _told(run: SceneRun) -> str:
    return "\n".join(f"> {one.prompt}\n{one.narration}" for one in run.exchanges[-TAIL_EXCHANGES:])


def _shape(model: type[BaseModel]) -> str:
    return json.dumps(schema_of(model), indent=2, ensure_ascii=False)


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    # Stripped: a brief read from a file ends in a newline, which would double the gap after it.
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def _recent(state: Game, limit: int) -> str:
    told = [
        f"> {one.prompt}\n[at {run.scene.title}] {one.narration}"
        for run in state.world.runs
        for one in run.exchanges
    ]
    return "\n\n".join(told[-limit:]) or "(the game has not started yet)"


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
