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
from aidm.core.io import read_character, read_scenario
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.hub import Offer
from aidm.engines.scenes.world import SceneCanon, SceneRun
from aidm.engines.seam import AnyEngine
from aidm.engines.twentyfourxx.world import (
    TwentyfourxxCharacterFile,
    TwentyfourxxGame,
    TwentyfourxxScenario,
)

SRD_PACK = "srd"
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
    world = state.payload
    assert list(world.player.items) == [COMM, CLIMBING_GEAR, NIGHT_VISION_GOGGLES]
    assert world.run.place == "docking-ring"
    assert PLAYER_ID not in world.present()


def test_a_scenario_with_no_packs_is_refused_by_check_packs() -> None:
    engine, state = _twentyfourxx_game()
    with pytest.raises(ValueError, match="at least one table set"):
        engine.validate(updated(state, packs=()))


def test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs() -> None:
    engine, state = _twentyfourxx_game()
    with pytest.raises(ValueError, match="not installed"):
        engine.validate(updated(state, packs=(SRD_PACK, "uninstalled")))


def test_check_game_refuses_a_campaign_meta_with_no_hub() -> None:
    engine, state = _twentyfourxx_game()
    campaign_meta = state.scenario.model_copy(update={"kind": "campaign"})
    with pytest.raises(ValueError, match="campaign"):
        engine.validate(updated(state, scenario=campaign_meta))


def test_check_game_refuses_a_hub_with_a_one_shot_meta() -> None:
    engine, state = _twentyfourxx_game()
    world = state.payload
    hub_payload = world.model_copy(
        update={
            "hub": world.run.place,
            "board": (
                Offer(title="Job One", pitch="I take job one."),
                Offer(title="Job Two", pitch="I take job two."),
            ),
        }
    )
    with pytest.raises(ValueError, match="one-shot"):
        engine.validate(updated(state, payload=hub_payload))


def test_restored_round_trips() -> None:
    engine, state = _twentyfourxx_game()
    assert engine.restore(state.model_dump_json()) == state


def test_a_player_id_cast_entry_is_refused_by_new_game() -> None:
    decoy = Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = TwentyfourxxScenario(
        meta=ScenarioMeta(title="Test", premise="A test scenario."),
        engine=TWENTYFOURXX,
        packs=(SRD_PACK,),
        payload=SceneCanon(
            cast={PLAYER_ID: decoy},
            opening=SceneRun(
                place="airlock",
                title="The Airlock",
                question="Can they reach the control deck before the air runs out?",
                situation="A" * 80,
            ),
        ),
    )
    character = read_character(CHARACTERS, "kael", TWENTYFOURXX, TwentyfourxxCharacterFile)
    with pytest.raises(ValueError, match="the player is in the cast"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(scenario, character)


def test_a_foreign_scenario_is_refused_by_new_game() -> None:
    character = read_character(CHARACTERS, "kael", TWENTYFOURXX, TwentyfourxxCharacterFile)
    foreign_scenario = read_scenario(SCENARIOS, "drowned-road", SCENARIO_MODELS)
    with pytest.raises(ValueError, match="incompatible scenario"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(foreign_scenario, character)


def test_a_foreign_character_is_refused_by_new_game() -> None:
    scenario = read_scenario(SCENARIOS, "silent-relay", SCENARIO_MODELS)
    breathless = ENGINES_BUILT[BREATHLESS]
    foreign_character = read_character(CHARACTERS, "kael", BREATHLESS, breathless.character)
    with pytest.raises(ValueError, match="incompatible character"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(scenario, foreign_character)
