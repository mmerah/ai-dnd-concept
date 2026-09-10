from random import Random

import pytest
from support.breathless import ENGINE, SKILLS_RATED
from support.table import (
    BREATHLESS,
    ENGINES_BUILT,
    change,
    game,
    narrowed,
    stub_worldsmith,
    updated,
)

from aidm.core.entities import EngineId, EntityId, Refusal
from aidm.core.io import decode
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.world import (
    STARTING_ITEM,
    BreathlessCharacter,
    BreathlessGame,
    BreathlessScenario,
    Supply,
    Survivor,
    SurvivorSheet,
)
from aidm.engines.hiring import HIRE, SIGNED_ON, Hire
from aidm.engines.scenes.packs import SRD_PACK
from aidm.engines.scenes.world import SceneCanon, SceneRun
from aidm.engines.seam import AnyEngine

FIRE_AXE = EntityId("fire-axe")
OVID = EntityId("ovid-sarn")


def _breathless_game() -> tuple[AnyEngine, BreathlessGame]:
    engine, state = game(BREATHLESS)
    state = narrowed(state, BreathlessGame)
    return engine, state


def test_the_shipped_game_begins_with_the_srd_pack_and_the_players_item() -> None:
    _, state = _breathless_game()
    assert state.packs == (SRD_PACK,)
    world = state.payload
    sheet = world.player.dice()
    assert sheet.items[FIRE_AXE].die == STARTING_ITEM
    assert sheet.pronouns == "he/him"
    assert sheet.job == "Park Ranger"
    assert PLAYER_ID not in world.present()


def test_join_party_lands_a_party_joined_fact_and_adds_the_member() -> None:
    engine, state = _breathless_game()
    draft = state.draft()

    _ = change(engine, draft, "join_party", entity_id=OVID)

    assert OVID in draft.payload.party


def test_a_scenario_with_no_packs_is_refused_by_check_packs() -> None:
    engine, state = _breathless_game()
    with pytest.raises(Refusal, match="at least one table set"):
        engine.validate(updated(state, packs=()))


def test_restored_round_trips() -> None:
    engine, state = _breathless_game()
    assert engine.restore(decode(state.model_dump_json())) == state


def test_a_player_id_cast_entry_is_refused_by_new_game() -> None:
    decoy = Survivor(id=PLAYER_ID, name="Someone", brief="filed wrongly", known=True)
    scenario = BreathlessScenario(
        meta=ScenarioMeta(title="Test", premise="A test scenario.", scope="One tense evening."),
        engine=EngineId("breathless"),
        packs=(SRD_PACK,),
        payload=SceneCanon[Survivor](
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
            sheet=SurvivorSheet(
                pronouns="he/him",
                job="Park Ranger",
                skills=SKILLS_RATED,
                worn=dict(SKILLS_RATED),
                items={FIRE_AXE: Supply(name="Fire Axe", die=STARTING_ITEM)},
            ),
        ),
    )
    with pytest.raises(Refusal, match="the player is in the cast"):
        ENGINES_BUILT[BREATHLESS].new_game(scenario, character)


def test_hire_sets_the_generation_and_ends_the_turn() -> None:
    _, state = _breathless_game()
    draft = state.draft()
    _ = ENGINE.hire(draft, Hire(entity_id=OVID, terms="Guide us across the flats"), Random(0))
    assert draft.generation is not None
    assert draft.generation.operation == HIRE
    assert draft.generation.target == OVID


def test_hire_refuses_a_sheeted_member() -> None:
    _, state = _breathless_game()
    draft = state.draft()
    draft.payload.cast[OVID].sheet = SurvivorSheet(skills=SKILLS_RATED, worn=dict(SKILLS_RATED))
    with pytest.raises(Refusal, match="already carries a sheet"):
        ENGINE.hire(draft, Hire(entity_id=OVID, terms="Guide us across the flats"), Random(0))


def test_validate_refuses_a_stale_hire_target() -> None:
    _, state = _breathless_game()
    draft = state.draft()
    _ = ENGINE.hire(draft, Hire(entity_id=OVID, terms="Guide us across the flats"), Random(0))
    draft.payload.cast[OVID].sheet = SurvivorSheet(skills=SKILLS_RATED, worn=dict(SKILLS_RATED))
    with pytest.raises(Refusal, match="already carries a sheet"):
        ENGINE.validate(draft)


async def test_advance_on_a_hire_installs_the_sheet_and_joins_the_party() -> None:
    _, state = _breathless_game()
    draft = state.draft()
    _ = ENGINE.hire(draft, Hire(entity_id=OVID, terms="Guide us across the flats"), Random(0))
    generation = draft.generation
    assert generation is not None

    answer = {
        "pronouns": "he/him",
        "job": "Bell-ringer",
        "skills": SKILLS_RATED,
        "item": "Boat hook",
    }
    _, message = await ENGINE.advance(draft, generation, stub_worldsmith(answer))

    member = draft.payload.cast[OVID]
    assert member.sheet is not None
    assert len(member.sheet.skills) == 6
    assert member.sheet.items[EntityId("boat-hook")].die == STARTING_ITEM
    assert OVID in draft.payload.party
    assert message == SIGNED_ON.format(name=member.name)
