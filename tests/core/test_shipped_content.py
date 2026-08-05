import pytest
from core_test_support import CHARACTERS, SCENARIOS, settings

from aidm.core.base import SAVE_VERSION, EngineId
from aidm.core.content import authored_world
from aidm.core.registry import build_engine, engine_ids
from aidm.core.store import load_character, load_scenario
from aidm.core.world import EngineRules, GameState


@pytest.mark.parametrize("engine_id", engine_ids())
def test_shipped_content_composes_under_every_registered_engine(engine_id: EngineId) -> None:
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault", engine_id)
    selected_character = load_character(CHARACTERS, "kael", engine_id)
    authored = authored_world(selected_scenario, selected_character)
    engine = build_engine(engine_id, settings())

    state: GameState[EngineRules] = engine.state_type(
        save_version=SAVE_VERSION,
        scenario_id=selected_scenario.id,
        character_id=selected_character.id,
        scenario=selected_scenario.meta,
        engine=engine.id,
        world=engine.initial_world(authored, selected_character.overlay.character),
    )

    engine.validate_state(state)
