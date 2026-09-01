import pytest
from core_test_support import (
    BREATHLESS,
    CHARACTERS,
    ENGINES_BUILT,
    SCENARIO_MODELS,
    SCENARIOS,
    TWENTYFOURXX,
    game,
    updated,
)

from aidm.core.entities import EntityId
from aidm.core.io import load_character, read_scenario
from aidm.core.model import ScenarioMeta
from aidm.engines.core import PLAYER_ID, AnyEngine
from aidm.engines.scenes import Scene
from aidm.engines.twentyfourxx.engine import new_game
from aidm.engines.twentyfourxx.tools import SRD_PACK
from aidm.engines.twentyfourxx.world import (
    Npc,
    SceneCanon,
    TwentyfourxxCharacterFile,
    TwentyfourxxGame,
    TwentyfourxxScenario,
    TwentyfourxxScenarioFile,
)

COMM = EntityId("comm")
CLIMBING_GEAR = EntityId("climbing-gear")
NIGHT_VISION_GOGGLES = EntityId("night-vision-goggles")


def _twentyfourxx_game() -> tuple[AnyEngine, TwentyfourxxGame]:
    engine, state = game(TWENTYFOURXX)
    if not isinstance(state, TwentyfourxxGame):
        raise AssertionError("the 24XX engine began another game type")
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_operators_gear() -> None:
    _, state = _twentyfourxx_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload.world
    assert list(world.player.items) == [COMM, CLIMBING_GEAR, NIGHT_VISION_GOGGLES]
    assert world.run.scene.place == "docking-ring"
    assert PLAYER_ID not in world.run.present


def test_a_scenario_with_no_packs_is_refused_by_check_packs() -> None:
    engine, state = _twentyfourxx_game()
    with pytest.raises(ValueError, match="at least one table set"):
        engine.validate(updated(state, packs=()))


def test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs() -> None:
    engine, state = _twentyfourxx_game()
    with pytest.raises(ValueError, match="not installed"):
        engine.validate(updated(state, packs=(SRD_PACK, "uninstalled")))


def test_restored_round_trips() -> None:
    engine, state = _twentyfourxx_game()
    assert engine.restored(state.model_dump_json()) == state


def test_a_player_id_cast_entry_is_refused_by_new_game() -> None:
    decoy = Npc(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = TwentyfourxxScenarioFile(
        meta=ScenarioMeta(title="Test", premise="A test scenario."),
        engine=TWENTYFOURXX,
        packs=(SRD_PACK,),
        payload=TwentyfourxxScenario(
            world=SceneCanon(
                cast={PLAYER_ID: decoy},
                opening=Scene(
                    place="airlock",
                    title="The Airlock",
                    question="Can they reach the control deck before the air runs out?",
                    situation="A" * 80,
                ),
            )
        ),
    )
    character = load_character(CHARACTERS, "kael", TWENTYFOURXX, TwentyfourxxCharacterFile)
    with pytest.raises(ValueError, match="reserved player id"):
        new_game(scenario, character)


def test_a_foreign_scenario_is_refused_by_new_game() -> None:
    character = load_character(CHARACTERS, "kael", TWENTYFOURXX, TwentyfourxxCharacterFile)
    foreign_scenario = read_scenario(SCENARIOS, "drowned-road", SCENARIO_MODELS)
    with pytest.raises(ValueError, match="incompatible scenario"):
        new_game(foreign_scenario, character)


def test_a_foreign_character_is_refused_by_new_game() -> None:
    scenario = read_scenario(SCENARIOS, "silent-relay", SCENARIO_MODELS)
    breathless = ENGINES_BUILT[BREATHLESS]
    foreign_character = load_character(CHARACTERS, "kael", BREATHLESS, breathless.character)
    with pytest.raises(ValueError, match="incompatible character"):
        new_game(scenario, foreign_character)
