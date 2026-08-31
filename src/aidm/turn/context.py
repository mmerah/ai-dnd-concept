import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel

from aidm.content.io import engine_text
from aidm.kernel.views import NarratorView
from aidm.kits.scenes.state import SceneState
from aidm.kits.scenes.views import SheetRows, entity_line, thread_lines
from aidm.state.model import Game, ScenarioMeta, SceneWrite
from aidm.state.play import Narration, PendingDecision
from aidm.state.tools import schema_of

ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)
SURPRISE = (
    "Surprise the player. Turn an established fact against them, or bring back something they "
    "have stopped thinking about. Surprise by recombining what exists, never by inventing what "
    "the source would not hold."
)

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
    world: SceneState[S],
    intent: str,
    include: Sequence[str],
    guidance: str,
    rows: SheetRows,
    *,
    opening: bool = False,
) -> str:
    """The whole material for one scene, assembled by code so no role has to remember it."""
    if opening:
        history = "(no scenes yet — write the opening)"
        cast = "(no cast yet — write the people and things this scene needs)"
    else:
        history = "\n\n".join(
            f"SCENE {number}: {one.title} ({one.place})\n{one.situation}"
            for number, one in enumerate((*world.played, world.current), start=1)
        )
        cast = "\n".join(entity_line(world, one, rows, where=True) for one in world.cast.values())
    return _sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", world.source or "(none — write from the threads and the cast)"),
            ("SCENES SO FAR", history),
            ("THE WHOLE CAST", cast),
            ("THREADS", thread_lines(world.threads.values(), standing_only=False)),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT COMES NEXT", intent),
            ("FACES TO BRING BACK (a hint, not an order)", ", ".join(include) or "(none)"),
            ("STANDING INSTRUCTION", SURPRISE),
            ("ANSWER WITH", _shape(SceneWrite)),
        )
    )


def _shape(model: type[BaseModel]) -> str:
    return json.dumps(schema_of(model), indent=2, ensure_ascii=False)


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    # Stripped: a brief read from a file ends in a newline, which would double the gap after it.
    return "\n\n".join(f"{name}:\n{body.strip()}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def told_passages(state: Game, limit: int) -> tuple[str, ...]:
    """What the player has already read, so continuity costs the narrator no hidden canon."""
    return tuple(one.narration for one in state.history[-limit:] if one.narration)


def _recent(state: Game, limit: int) -> str:
    told = [
        f"> {exchange.prompt}\n[at {exchange.scene}] {exchange.narration}"
        for exchange in state.history[-limit:]
    ]
    return "\n\n".join(told) or "(the game has not started yet)"


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
