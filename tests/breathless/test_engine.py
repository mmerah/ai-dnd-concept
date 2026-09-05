import pytest
from support.breathless import SKILLS_RATED
from support.table import BREATHLESS, ENGINES_BUILT, game, narrowed, updated

from aidm.core.entities import EngineId, EntityId, Refusal
from aidm.core.io import decode
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, SRD_PACK, Person
from aidm.engines.breathless.world import (
    STARTING_ITEM,
    BreathlessCharacter,
    BreathlessGame,
    BreathlessScenario,
    Item,
    Survivor,
)
from aidm.engines.scenes.world import SceneCanon, SceneRun
from aidm.engines.seam import AnyEngine

FIRE_AXE = EntityId("fire-axe")


def _breathless_game() -> tuple[AnyEngine, BreathlessGame]:
    engine, state = game(BREATHLESS)
    state = narrowed(state, BreathlessGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_players_item() -> None:
    _, state = _breathless_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload
    assert world.player.items[FIRE_AXE].die == STARTING_ITEM
    assert PLAYER_ID not in world.present()


def test_a_scenario_with_no_packs_is_refused_by_check_packs() -> None:
    engine, state = _breathless_game()
    with pytest.raises(Refusal, match="at least one table set"):
        engine.validate(updated(state, packs=()))


def test_restored_round_trips() -> None:
    engine, state = _breathless_game()
    assert engine.restore(decode(state.model_dump_json())) == state


def test_a_player_id_cast_entry_is_refused_by_new_game() -> None:
    decoy = Person(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = BreathlessScenario(
        meta=ScenarioMeta(title="Test", premise="A test scenario.", scope="One tense evening."),
        engine=EngineId("breathless"),
        packs=(SRD_PACK,),
        payload=SceneCanon(
            cast={PLAYER_ID: decoy},
            opening=SceneRun(
                place="alley",
                title="The Alley",
                focus="Can they lose the mob in the alley?",
                situation="A" * 80,
            ),
        ),
    )
    character = BreathlessCharacter(
        id="kael",
        engine=EngineId("breathless"),
        payload=Survivor(
            id=PLAYER_ID,
            name="Kael",
            brief="A wary ranger.",
            known=True,
            pronouns="he/him",
            job="Park Ranger",
            skills=SKILLS_RATED,
            worn=SKILLS_RATED,
            items={FIRE_AXE: Item(name="Fire Axe", die=STARTING_ITEM)},
        ),
    )
    with pytest.raises(Refusal, match="the player is in the cast"):
        ENGINES_BUILT[BREATHLESS].new_game(scenario, character)
