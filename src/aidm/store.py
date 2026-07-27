"""JSON persistence. A save is exactly one GameState; the trace is append-only JSONL; a pack is a
directory of records."""

from functools import cache
from pathlib import Path

from . import content
from .config import settings
from .domain.models import (
    SAVE_VERSION,
    CharacterSheet,
    GameState,
    ScenarioDef,
    Turn,
)
from .engine import bestiary

ENCODING = "utf-8"  # narration is full of curly quotes; the platform default is not enough


def _save_path(slug: str) -> Path:
    return settings().saves_dir / f"{slug}.json"


def _trace_path(slug: str) -> Path:
    return settings().saves_dir / f"{slug}.trace.jsonl"


@cache
def library() -> content.Library:
    """The packs this build plays, read once — the pack list cannot change within a run."""
    return content.load(settings().packs)


def new_game(scenario: str, character: str = "kael") -> GameState:
    """Read a scenario definition and an independent character; the domain composes the state."""
    conf = settings()
    definition = ScenarioDef.model_validate_json(
        (conf.scenarios_dir / f"{scenario}.json").read_text(encoding=ENCODING)
    )
    sheet = CharacterSheet.model_validate_json(
        (conf.characters_dir / f"{character}.json").read_text(encoding=ENCODING)
    )
    packs = library()
    return bestiary.statted_world(GameState.from_scenario(definition, sheet, packs.stamps), packs)


def load(slug: str) -> GameState | None:
    """A save is unreadable if either the schema or the content under it moved: an entity's stats
    were snapshotted from a pack version, so a bump would silently change the game it recorded."""
    path = _save_path(slug)
    if not path.exists():
        return None
    state = GameState.model_validate_json(path.read_text(encoding=ENCODING))
    if state.version != SAVE_VERSION:
        raise ValueError(f"save {slug!r} is v{state.version}, this build needs v{SAVE_VERSION}")
    current = library().stamps
    if state.packs != current:
        raise ValueError(
            f"save {slug!r} was played against {state.packs}, this build ships {current}"
        )
    return state


def save(slug: str, state: GameState) -> None:
    path = _save_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding=ENCODING)


def append_trace(slug: str, turn: Turn) -> None:
    """Write-only and unversioned: stamp a version before anything reads this back."""
    path = _trace_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding=ENCODING) as f:
        f.write(turn.model_dump_json() + "\n")


def reset(slug: str) -> None:
    _save_path(slug).unlink(missing_ok=True)
    _trace_path(slug).unlink(missing_ok=True)
