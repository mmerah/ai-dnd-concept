import pytest
from support.tunnelgoons import HALL, MIRA, START, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.engines.rooms.world import Item, RoomCanon, Visit, Way
from aidm.engines.tunnelgoons.world import Npc, TunnelGoonsWorld

GHOST = EntityId("ghost")


def test_begin_refuses_a_canon_whose_npc_stands_in_no_place() -> None:
    world = small_world().payload
    canon = RoomCanon[Npc](
        places=world.places, ways=world.ways, npcs=world.npcs, items=world.items, start=START
    )
    canon.npcs[MIRA].place = GHOST
    with pytest.raises(Refusal, match="in no place"):
        _ = TunnelGoonsWorld.begin(canon, world.player, ())


def test_an_item_on_nothing_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.items[EntityId("stray")] = Item(
        id=EntityId("stray"), name="Stray", brief="Nobody's", known=True, on=GHOST
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
    draft.payload.visits.append(Visit(place=HALL))
    assert draft.commit().payload.current.id == HALL


def test_walk_reaches_every_place_along_the_ways() -> None:
    world = small_world().payload
    assert world.reachable(START) == set(world.places)


def test_frontier_counts_the_one_unknown_place_past_a_known_one() -> None:
    world = small_world().payload
    assert world.frontier() == 1


def test_the_map_so_far_names_who_stands_where_and_every_id_in_use() -> None:
    state = small_world()

    shown = state.payload.map_so_far()

    assert "  here: Mira[mira] (met), Lantern[lantern] (met)" in shown
    assert "Robo Mantis" not in shown
    assert shown.endswith(
        "ids in use: crypt, hall, key, lantern, mantis, mira, rope, start, torch, vault"
    )
