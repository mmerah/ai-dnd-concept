"""Where a game begins, or resumes: a scenario, a sheet and a pack list composed into a `GameState`.

Composition, not I/O — the caller reads the files and hands the values here, so beginning a game is
testable without any of them. Each step needs the ruleset, which is exactly what `domain/` may not
read; the stamps travel alongside it, because which packs were played is persistence, not a rule."""

from collections.abc import Sequence

from ..content import PackStamp
from ..domain.models import SAVE_VERSION, CharacterSheet, GameState, ScenarioDef
from . import bestiary, progression
from .ruleset import Ruleset


def begin(
    scenario: ScenarioDef, sheet: CharacterSheet, ruleset: Ruleset, packs: Sequence[PackStamp]
) -> GameState:
    """A level-1 character over the scenario's canon, with every ref statted. Starting items are
    statted too, so an item the sheet names meets the same load-time check as authored canon."""
    start = progression.first_level(sheet, ruleset)
    state = GameState.from_scenario(scenario, sheet, packs, start)
    return bestiary.statted_world(state, ruleset)


def resumable(state: GameState, packs: Sequence[PackStamp]) -> GameState:
    """A save this build may still play, or a raise. Unreadable if either the schema or the content
    under it moved: an entity's stats were snapshotted from a pack version, so a bump would silently
    change the game the save recorded. There are no migrations — fail loudly instead."""
    if state.version != SAVE_VERSION:
        raise ValueError(f"save is v{state.version}, this build needs v{SAVE_VERSION}")
    if list(state.packs) != list(packs):
        raise ValueError(f"save was played against {state.packs}, this build ships {list(packs)}")
    return state
