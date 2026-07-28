from collections.abc import Sequence

from ..content import PackStamp
from ..domain.models import SAVE_VERSION, CharacterSheet, GameState, ScenarioDef
from . import bestiary, progression
from .ruleset import Ruleset


def begin(
    scenario: ScenarioDef, sheet: CharacterSheet, ruleset: Ruleset, packs: Sequence[PackStamp]
) -> GameState:
    start = progression.first_level(sheet, ruleset)
    state = GameState.from_scenario(scenario, sheet, packs, start)
    return bestiary.statted_world(state, ruleset)


def resumable(state: GameState, packs: Sequence[PackStamp]) -> GameState:
    """Reject saves whose schema or snapshotted content changed."""
    if state.version != SAVE_VERSION:
        raise ValueError(f"save is v{state.version}, this build needs v{SAVE_VERSION}")
    if list(state.packs) != list(packs):
        raise ValueError(f"save was played against {state.packs}, this build ships {list(packs)}")
    return state
