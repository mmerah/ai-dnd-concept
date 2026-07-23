"""JSON persistence. A save is exactly one GameState; the trace is append-only JSONL."""

from pathlib import Path

from .config import settings
from .domain.models import SAVE_VERSION, GameState
from .domain.turn import Turn

ENCODING = "utf-8"  # narration is full of curly quotes; the platform default is not enough


def _save_path(slug: str) -> Path:
    return settings().saves_dir / f"{slug}.json"


def _trace_path(slug: str) -> Path:
    return settings().saves_dir / f"{slug}.trace.jsonl"


def new_game(scenario: str) -> GameState:
    """A scenario file is a starting GameState."""
    path = settings().scenarios_dir / f"{scenario}.json"
    return GameState.model_validate_json(path.read_text(encoding=ENCODING))


def load(slug: str) -> GameState | None:
    path = _save_path(slug)
    if not path.exists():
        return None
    state = GameState.model_validate_json(path.read_text(encoding=ENCODING))
    if state.version != SAVE_VERSION:
        raise ValueError(f"save {slug!r} is v{state.version}, this build needs v{SAVE_VERSION}")
    return state


def save(slug: str, state: GameState) -> None:
    path = _save_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding=ENCODING)


def append_trace(slug: str, turn: Turn) -> None:
    path = _trace_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding=ENCODING) as f:
        f.write(turn.model_dump_json() + "\n")


def reset(slug: str) -> None:
    _save_path(slug).unlink(missing_ok=True)
    _trace_path(slug).unlink(missing_ok=True)
