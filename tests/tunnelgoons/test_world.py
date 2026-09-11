import pytest
from support.tunnelgoons import HALL, MIRA, START, small_world

from aidm.core.entities import Refusal
from aidm.engines.rooms.world import MapDraft, Prop, Way
from aidm.engines.tunnelgoons.world import GoonSheet, Npc, TunnelGoonsWorld

GHOST = "ghost"


def test_begin_refuses_a_draft_whose_npc_stands_in_no_place() -> None:
    world = small_world().payload
    draft = MapDraft[Npc](
        places=world.places, ways=world.ways, npcs=world.npcs, items=world.items, start=START
    )
    draft.npcs[MIRA].place = GHOST
    with pytest.raises(Refusal, match="in no place"):
        _ = TunnelGoonsWorld.opening(draft, world.player, (), "")


def test_an_item_on_nothing_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.items["stray"] = Prop(
        id="stray", name="Stray", brief="Nobody's", known=True, on=GHOST
    )
    with pytest.raises(Refusal, match="on nothing"):
        _ = draft.commit()


def test_an_npc_in_no_place_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.npcs[MIRA].place = GHOST
    with pytest.raises(Refusal, match="no place"):
        _ = draft.commit()


def test_a_way_to_a_non_place_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.ways[START].append(Way(to=GHOST))
    with pytest.raises(Refusal, match="not a place"):
        _ = draft.commit()


def test_the_player_stands_at_the_last_visit() -> None:
    draft = small_world().draft()
    draft.payload.visits.append(HALL)
    assert draft.commit().payload.current.id == HALL


def test_walk_reaches_every_place_along_the_ways() -> None:
    world = small_world().payload
    assert world.reachable(START) == set(world.places)


def test_frontier_counts_the_one_unknown_place_past_a_known_one() -> None:
    world = small_world().payload
    assert world.frontier() == 1


def test_a_goons_rows_put_health_before_the_sheets_rows() -> None:
    world = small_world().payload

    labels = [label for label, _ in world.player.rows()]

    assert labels == ["Health", "Brute", "Skulker", "Erudite", "Inventory", "Level"]


def test_the_player_levels_up_their_ability_and_health_with_no_name_prefix() -> None:
    world = small_world().payload
    player = world.player
    sheet = player.require_sheet()
    before_ability = sheet.abilities["brute"]
    before_hp = player.hp.maximum

    facts = player.level("brute", "health")

    assert sheet.abilities["brute"] == before_ability + 1
    assert player.hp.maximum == before_hp + 1
    assert player.hp.current == before_hp + 1
    assert sheet.level == 2
    assert len(facts) == 1
    assert facts[0].card == "Level 2: Brute +1, Health +1"
    assert facts[0].trace == facts[0].card


def test_a_hired_npc_levels_up_their_ability_and_inventory_with_a_name_prefix() -> None:
    world = small_world().payload
    mira = world.npcs[MIRA]
    mira.sheet = GoonSheet(abilities={"brute": 0, "skulker": 0, "erudite": 0})
    before_inventory = mira.require_sheet().inventory

    facts = mira.level("skulker", "inventory")

    assert mira.require_sheet().abilities["skulker"] == 1
    assert mira.require_sheet().inventory == before_inventory + 1
    assert mira.require_sheet().level == 2
    assert len(facts) == 1
    assert facts[0].card == "Mira: Level 2: Skulker +1, Inventory +1"


def test_the_map_so_far_names_who_stands_where_and_every_id_in_use() -> None:
    state = small_world()

    shown = state.payload.map_so_far()

    assert "  here: Mira[mira] (met), Lantern[lantern] (met)" in shown
    assert "Robo Mantis" not in shown
    assert shown.endswith(
        "ids in use: crypt, hall, key, lantern, mantis, mira, rope, start, torch, vault"
    )
