import pytest
from core_test_support import updated
from tunnelgoons_test_support import HALL, MIRA, START, TAVERN, hub_world, small_world

from aidm.core.entities import EntityId
from aidm.engines.hub import Debrief
from aidm.engines.tunnelgoons.world import Item, Visit, Way, frontier, has_shortcut, walk

GHOST = EntityId("ghost")


def test_an_item_on_nothing_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.world.items[EntityId("stray")] = Item(
        id=EntityId("stray"), name="Stray", brief="Nobody's", known=True, on=GHOST
    )
    with pytest.raises(ValueError, match="on nothing"):
        _ = draft.committed()


def test_an_npc_in_no_place_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.world.npcs[MIRA].place = GHOST
    with pytest.raises(ValueError, match="no place"):
        _ = draft.committed()


def test_a_way_to_a_non_place_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.world.ways[START] = (*draft.payload.world.ways[START], Way(to=GHOST))
    with pytest.raises(ValueError, match="not a place"):
        _ = draft.committed()


def test_a_visit_off_the_player_is_refused() -> None:
    draft = small_world().draft()
    draft.payload.world.visits.append(Visit(place=HALL))
    with pytest.raises(ValueError, match="not where the player stands"):
        _ = draft.committed()


def test_walk_reaches_every_place_along_the_ways() -> None:
    world = small_world().payload.world
    assert walk(world.ways, START) == set(world.places)


def test_has_shortcut_finds_the_alternate_route_to_the_vault() -> None:
    world = small_world().payload.world
    assert has_shortcut(world.ways)


def test_frontier_counts_the_one_unknown_place_past_a_known_one() -> None:
    world = small_world().payload.world
    assert frontier(world) == 1


def test_a_debrief_on_a_visit_away_from_the_hub_is_refused() -> None:
    world = hub_world().payload.world
    with pytest.raises(ValueError, match="debrief away from the hub"):
        _ = updated(
            world,
            visits=[
                Visit(place=TAVERN),
                Visit(place=START, debrief=Debrief(text="Job's done.", finished=True)),
                Visit(place=TAVERN),
            ],
        )


def test_a_job_stamp_with_no_hub_is_refused() -> None:
    world = small_world().payload.world
    with pytest.raises(ValueError, match="job with no hub"):
        _ = updated(world, visits=[Visit(place=START, job="Bandits")])
