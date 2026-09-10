import pytest
from support.table import (
    ENGINES_BUILT,
    LIBRARY,
    TWENTYFOURXX,
    change,
    game,
    narrowed,
    updated,
)

from aidm.core.entities import Refusal
from aidm.core.io import decode
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.scenes.world import SceneCanon, SceneRun
from aidm.engines.seam import AnyEngine
from aidm.engines.twentyfourxx.world import (
    Crewmate,
    TwentyfourxxCharacter,
    TwentyfourxxGame,
    TwentyfourxxScenario,
)

COMM = "comm"
CLIMBING_GEAR = "climbing-gear"
NIGHT_VISION_GOGGLES = "night-vision-goggles"
VESSA = "vessa-rune"


def _twentyfourxx_game() -> tuple[AnyEngine, TwentyfourxxGame]:
    engine, state = game(TWENTYFOURXX)
    state = narrowed(state, TwentyfourxxGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_operators_gear() -> None:
    _, state = _twentyfourxx_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload
    assert list(world.player.dice().items) == [COMM, CLIMBING_GEAR, NIGHT_VISION_GOGGLES]
    assert world.run.place == "docking-ring"
    assert PLAYER_ID not in world.present()


def test_join_party_lands_a_party_joined_fact_and_adds_the_member() -> None:
    engine, state = _twentyfourxx_game()
    draft = state.draft()

    _ = change(engine, draft, "join_party", entity_id=VESSA)

    assert VESSA in draft.payload.party


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
    decoy = Crewmate(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = TwentyfourxxScenario(
        meta=ScenarioMeta(title="Test", premise="A test scenario.", scope="One tense night."),
        engine=TWENTYFOURXX,
        packs=(SRD_PACK,),
        payload=SceneCanon[Crewmate](
            cast={PLAYER_ID: decoy},
            opening=SceneRun(
                place="airlock",
                title="The Airlock",
                focus="Can they reach the control deck before the air runs out?",
                situation="A" * 80,
            ),
        ),
    )
    character = LIBRARY.read_character("kael", TWENTYFOURXX, TwentyfourxxCharacter)
    with pytest.raises(Refusal, match="the player is in the cast"):
        ENGINES_BUILT[TWENTYFOURXX].new_game(scenario, character)
