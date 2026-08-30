from collections.abc import Iterable, Sequence
from pathlib import Path

from aidm.content.io import engine_text
from aidm.kernel.views import NarratorView
from aidm.state.model import ScenarioMeta

ANSWERED_BY_OPTION = (
    "The player chose the option above and the rules have applied it. Develop what it caused; "
    "do not settle it again."
)


def render_director(
    sections: Sequence[tuple[str, str]],
    scenario: ScenarioMeta,
    prompt: str,
    *,
    resumed: str = "",
    notes: Sequence[str] = (),
) -> str:
    """Generic framing only; the engine states every section, and the action reads last."""
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
            *sections,
            ("NOTES FROM THE RULES", "\n".join(f"- {note}" for note in notes) or "- (none)"),
            *ending,
        )
    )


def render_narrator(
    view: NarratorView, scenario: ScenarioMeta, *, evidence: str, prompt: str
) -> str:
    return _sections(
        (
            _premise(scenario),
            ("SCENE", f"{view.title}\n{view.situation}"),
            (
                "WHO IS HERE",
                "\n".join(f"- {one.name} — {one.brief}" for one in view.subjects) or "- (none)",
            ),
            ("WHAT HAPPENED", evidence),
            ("PLAYER ACTION", prompt),
        )
    )


def _sections(parts: Iterable[tuple[str, str]]) -> str:
    return "\n\n".join(f"{name}:\n{body}" for name, body in parts)


def _premise(scenario: ScenarioMeta) -> tuple[str, str]:
    return "SCENARIO", f"{scenario.title}\n{scenario.premise}"


_PROMPTS_DIR = Path(__file__).parent / "prompts"

DIRECTOR = engine_text(_PROMPTS_DIR / "director.md")
NARRATOR = engine_text(_PROMPTS_DIR / "narrator.md")


def director_instructions(engine_instructions: str) -> str:
    return f"{DIRECTOR}\n\n{engine_instructions}"
