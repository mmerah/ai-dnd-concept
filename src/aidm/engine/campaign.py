"""Where a game begins: a scenario, a sheet and a pack list composed into the first `GameState`.

Composition, not I/O — `store` reads the files and hands the values here, so beginning a game is
testable without any of them. Each step needs a pack, which is exactly what `domain/` may not read.
"""

from ..content import Library
from ..domain.models import CharacterSheet, GameState, ScenarioDef
from . import bestiary, progression


def begin(scenario: ScenarioDef, sheet: CharacterSheet, library: Library) -> GameState:
    """A level-1 character over the scenario's canon, with every ref statted. Starting items are
    statted too, so an item the sheet names meets the same load-time check as authored canon."""
    start = progression.first_level(sheet, library)
    state = GameState.from_scenario(scenario, sheet, library.stamps, start)
    return bestiary.statted_world(state, library)
