import pytest
from support.table import the_campaign
from support.tunnelgoons import HALL, MIRA, START, TAVERN, hub_world, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.engines.hub import Attempt, Job
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


def test_has_shortcut_finds_the_alternate_route_to_the_vault() -> None:
    world = small_world().payload
    assert world.has_shortcut()


def test_frontier_counts_the_one_unknown_place_past_a_known_one() -> None:
    world = small_world().payload
    assert world.frontier() == 1


def test_move_off_the_tavern_walks_a_reopened_jobs_last_attempt() -> None:
    state = hub_world()
    world = state.payload
    world.visits = [Visit(place=TAVERN), Visit(place=START), Visit(place=TAVERN)]
    job = Job(title="Bandits", place=START, attempts=[Attempt(started=1, returned=2)])
    campaign = the_campaign(world.campaign)
    campaign.jobs = [job]
    campaign.reopen(job, started=None)

    world.move(START, ())

    assert len(job.attempts) == 2
    assert job.attempts[-1].started == len(world.visits) - 1


def test_a_returned_that_is_not_a_tavern_visit_is_refused() -> None:
    draft = hub_world().draft()
    world = draft.payload
    world.visits = [Visit(place=TAVERN), Visit(place=START), Visit(place=HALL)]
    the_campaign(world.campaign).jobs = [
        Job(title="Bandits", place=START, attempts=[Attempt(started=1, returned=2)])
    ]
    with pytest.raises(Refusal, match="returned away from the hub"):
        _ = draft.commit()


def test_walked_places_leaves_out_the_current_visit_and_lists_a_place_once() -> None:
    state = hub_world()
    world = state.payload
    world.visits = [
        Visit(place=TAVERN),
        Visit(place=START),
        Visit(place=HALL),
        Visit(place=START),
        Visit(place=TAVERN),
    ]
    job = Job(title="Bandits", place=START, attempts=[Attempt(started=1)])
    the_campaign(world.campaign).jobs = [job]

    assert world.walked_places(job) == (START, HALL)
