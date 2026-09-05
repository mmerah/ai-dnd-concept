import pytest
from support.table import (
    BREATHLESS,
    ENGINES_BUILT,
    LIBRARY,
    SCENARIO_MODELS,
    TWENTYFOURXX,
    game,
    narrowed,
    updated,
)

from aidm.core.entities import EntityId, Refusal
from aidm.core.io import decode
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, Person
from aidm.engines.scenes.world import SceneCanon, SceneRun
from aidm.engines.seam import AnyEngine
from aidm.engines.twentyfourxx.world import (
    TwentyfourxxCharacter,
    TwentyfourxxGame,
    TwentyfourxxScenario,
)

SRD_PACK = "srd"
COMM = EntityId("comm")
CLIMBING_GEAR = EntityId("climbing-gear")
NIGHT_VISION_GOGGLES = EntityId("night-vision-goggles")


def _twentyfourxx_game() -> tuple[AnyEngine, TwentyfourxxGame]:
    engine, state = game(TWENTYFOURXX)
    state = narrowed(state, TwentyfourxxGame)
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
    with pytest.raises(Refusal, match="at least one table set"):
        engine.validate(updated(state, packs=()))


def test_a_scenario_with_an_uninstalled_pack_is_refused_by_check_packs() -> None:
    engine, state = _twentyfourxx_game()
    with pytest.raises(Refusal, match="not installed"):
        engine.validate(updated(state, packs=(SRD_PACK, "uninstalled")))


def test_restored_round_trips() -> None:
    engine, state = _twentyfourxx_game()
    assert engine.restore(decode(state.model_dump_json())) == state


def test_a_player_id_cast_entry_is_refused_by_new_game() -> None:
    decoy = Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = TwentyfourxxScenario(
        meta=ScenarioMeta(title="Test", premise="A test scenario.", scope="One tense night."),
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
    character = LIBRARY.read_character("kael", TWENTYFOURXX, TwentyfourxxCharacter)
    with pytest.raises(Refusal, match="the player is in the cast"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(scenario, character)


def test_a_foreign_scenario_is_refused_by_new_game() -> None:
    character = LIBRARY.read_character("kael", TWENTYFOURXX, TwentyfourxxCharacter)
    foreign_scenario = LIBRARY.read_scenario("drowned-road", SCENARIO_MODELS)
    with pytest.raises(Refusal, match="incompatible scenario"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(foreign_scenario, character)


def test_a_foreign_character_is_refused_by_new_game() -> None:
    scenario = LIBRARY.read_scenario("silent-relay", SCENARIO_MODELS)
    breathless = ENGINES_BUILT[BREATHLESS]
    foreign_character = LIBRARY.read_character("kael", BREATHLESS, breathless.character)
    with pytest.raises(Refusal, match="incompatible character"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(scenario, foreign_character)
