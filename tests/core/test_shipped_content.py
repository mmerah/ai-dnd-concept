import pytest
from core_test_support import CHARACTERS, SCENARIOS, settings

from aidm.app.session import build_engine
from aidm.content.authored import authored_world
from aidm.content.store import load_character, load_scenario
from aidm.engines.loader import engine_ids
from aidm.state.base import SAVE_VERSION, EngineId
from aidm.state.world import GameState


@pytest.mark.parametrize("engine_id", engine_ids())
def test_shipped_content_composes_under_every_registered_engine(engine_id: EngineId) -> None:
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault", engine_id)
    selected_character = load_character(CHARACTERS, "kael", engine_id)
    authored = authored_world(selected_scenario, selected_character)
    engine = build_engine(engine_id, settings())

    state = GameState(
        save_version=SAVE_VERSION,
        scenario_id=selected_scenario.id,
        character_id=selected_character.id,
        scenario=selected_scenario.meta,
        engine=engine.id,
        world=engine.initial_world(authored, selected_character.overlay.character),
    )

    engine.validate_state(state)
