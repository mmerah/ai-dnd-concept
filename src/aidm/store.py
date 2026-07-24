"""JSON persistence. A save is exactly one GameState; the trace is append-only JSONL."""

from pathlib import Path

from .config import settings
from .domain.models import (
    SAVE_VERSION,
    Character,
    CharacterSheet,
    GameState,
    ScenarioDef,
)
from .domain.turn import Turn

ENCODING = "utf-8"  # narration is full of curly quotes; the platform default is not enough


def _save_path(slug: str) -> Path:
    return settings().saves_dir / f"{slug}.json"


def _trace_path(slug: str) -> Path:
    return settings().saves_dir / f"{slug}.trace.jsonl"


def new_game(scenario: str, character: str = "kael") -> GameState:
    """Compose a starting GameState from a scenario definition and an independent character."""
    conf = settings()
    scenario_path = conf.scenarios_dir / f"{scenario}.json"
    character_path = conf.characters_dir / f"{character}.json"
    definition = ScenarioDef.model_validate_json(scenario_path.read_text(encoding=ENCODING))
    sheet = CharacterSheet.model_validate_json(character_path.read_text(encoding=ENCODING))
    return GameState(
        character=Character(**sheet.model_dump(), location_id=definition.starting_location_id),
        scenario=definition.meta,
        world=definition.as_world(),
    )


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
