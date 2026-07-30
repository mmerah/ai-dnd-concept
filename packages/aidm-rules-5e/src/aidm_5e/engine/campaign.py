from ..domain.models.state import CharacterSheet, GameState, ScenarioDef
from . import bestiary, progression
from .ruleset import Ruleset


def begin(scenario: ScenarioDef, sheet: CharacterSheet, ruleset: Ruleset) -> GameState:
    start = progression.first_level(sheet, ruleset)
    state = GameState.from_scenario(scenario, sheet, ruleset.stamps, start)
    return bestiary.statted_world(state, ruleset)
