from collections.abc import Iterable, Sequence
from pathlib import Path

from aidm.content.io import engine_text
from aidm.state.model import ScenarioMeta, Thread
from aidm.state.scene import Scene, VisibleScene

ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)


def render_director(
    scene: Scene,
    scenario: ScenarioMeta,
    threads: Sequence[Thread],
    prompt: str,
    *,
    resumed: str = "",
    notes: Sequence[str] = (),
) -> str:
    """Generic framing only; the situation is `Scene.sections`, and the action reads last."""
    # A chosen option is already applied: shown as its own words, a weak model settles it twice.
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
            _premise(scenario),
            *(
                (section.title, section.player if section.director is None else section.director)
                for section in scene.sections
            ),
            ("ACTIVE THREADS", _threads(threads)),
            ("NOTES FROM THE RULES", "\n".join(f"- {note}" for note in notes) or "- (none)"),
            *ending,
        )
    )


def render_narrator(
    scene: VisibleScene, scenario: ScenarioMeta, *, evidence: str, prompt: str
) -> str:
    return _sections(
        (
            _premise(scenario),
            *scene.sections,
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
        )
    )


def active_threads(threads: Iterable[Thread]) -> tuple[Thread, ...]:
    return tuple(
        sorted(
            (thread for thread in threads if thread.status != "resolved"),
            key=lambda thread: thread.title,
        )
    )


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


def _threads(threads: Sequence[Thread]) -> str:
    return "\n".join(_thread_line(thread) for thread in threads) or "- (none)"


def _thread_line(thread: Thread) -> str:
    line = f"- {thread.title}[{thread.id}] — status {thread.status}"
    return f"{line}\n  note: {thread.note}" if thread.note else line


_PROMPTS_DIR = Path(__file__).parent / "prompts"

DIRECTOR = engine_text(_PROMPTS_DIR / "director.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")


def director_instructions(engine_instructions: str) -> str:
    return f"{DIRECTOR}\n\n{engine_instructions}"
