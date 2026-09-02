import pytest
from core_test_support import BREATHLESS, ENGINES_BUILT, game, updated

from aidm.core.entities import EngineId, EntityId
from aidm.core.model import ScenarioMeta
from aidm.engines.breathless.tools import SRD_PACK
from aidm.engines.breathless.world import (
    STARTING_ITEM,
    BreathlessCharacter,
    BreathlessCharacterFile,
    BreathlessGame,
    BreathlessScenarioFile,
)
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.hub import Offer
from aidm.engines.scenes.world import Scene, SceneCanon, SceneScenario
from aidm.engines.seam import AnyEngine

FIRE_AXE = EntityId("fire-axe")


def _breathless_game() -> tuple[AnyEngine, BreathlessGame]:
    engine, state = game(BREATHLESS)
    if not isinstance(state, BreathlessGame):
        raise AssertionError("the Breathless engine began another game type")
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_players_item() -> None:
    _, state = _breathless_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload.world
    assert world.player.items[FIRE_AXE].die == STARTING_ITEM
    assert PLAYER_ID not in world.run.present


def test_a_scenario_with_no_packs_is_refused_by_check_packs() -> None:
    engine, state = _breathless_game()
    with pytest.raises(ValueError, match="at least one table set"):
        engine.validate(updated(state, packs=()))


def test_check_game_refuses_a_campaign_meta_with_no_hub() -> None:
    engine, state = _breathless_game()
    campaign_meta = state.scenario.model_copy(update={"kind": "campaign"})
    with pytest.raises(ValueError, match="campaign"):
        engine.validate(updated(state, scenario=campaign_meta))


def test_check_game_refuses_a_hub_with_a_one_shot_meta() -> None:
    engine, state = _breathless_game()
    world = state.payload.world
    hub_payload = state.payload.model_copy(
        update={
            "world": world.model_copy(
                update={
                    "hub": world.run.scene.place,
                    "board": (
                        Offer(title="Job One", pitch="I take job one."),
                        Offer(title="Job Two", pitch="I take job two."),
                    ),
                }
            )
        }
    )
    with pytest.raises(ValueError, match="one-shot"):
        engine.validate(updated(state, payload=hub_payload))


def test_restored_round_trips() -> None:
    engine, state = _breathless_game()
    assert engine.restored(state.model_dump_json()) == state


def test_a_player_id_cast_entry_is_refused_by_new_game() -> None:
    decoy = Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = BreathlessScenarioFile(
        meta=ScenarioMeta(title="Test", premise="A test scenario."),
        engine=EngineId("breathless"),
        packs=(SRD_PACK,),
        payload=SceneScenario(
            world=SceneCanon(
                cast={PLAYER_ID: decoy},
                opening=Scene(
                    place="alley",
                    title="The Alley",
                    question="Can they lose the mob in the alley?",
                    situation="A" * 80,
                ),
            )
        ),
    )
    character = BreathlessCharacterFile(
        id="kael",
        engine=EngineId("breathless"),
        name="Kael",
        brief="A wary ranger.",
        payload=BreathlessCharacter(
            pronouns="he/him",
            job="Park Ranger",
            skills={"think": 10, "sneak": 8, "bash": 6},
            item="Fire Axe",
        ),
    )
    with pytest.raises(ValueError, match="the player is in the cast"):
        ENGINES_BUILT[BREATHLESS].new_game(scenario, character)
