import pytest
from core_test_support import CHARACTERS, SCENARIOS

from aidm.app.session import begin_game, build_engine
from aidm.content.store import load_character, load_scenario
from aidm.engines.loader import engine_ids
from aidm.state.base import EngineId


@pytest.mark.parametrize("engine_id", engine_ids())
def test_shipped_content_composes_under_every_registered_engine(engine_id: EngineId) -> None:
    engine = build_engine(engine_id)
    binding = engine.binding()
    selected_scenario = load_scenario(SCENARIOS, "whispering-vault", binding)
    selected_character = load_character(CHARACTERS, "kael", binding)

    begin_game(engine, selected_scenario, selected_character)
