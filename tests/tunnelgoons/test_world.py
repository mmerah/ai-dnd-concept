import pytest
from support.table import the_campaign
from support.tunnelgoons import HALL, MIRA, START, TAVERN, hub_world, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.engines.hub import Job
from aidm.engines.rooms.world import Dungeon, Item, Place, RoomCanon, Visit, Way
from aidm.engines.tunnelgoons.world import Npc, TunnelGoonsWorld

GHOST = EntityId("ghost")
OLD_SITE = EntityId("old-site")
NEW_SITE = EntityId("new-site")
BANDITS = "Bandits"


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


def test_move_tags_each_new_visit_with_the_open_job_even_back_at_the_tavern() -> None:
    world = hub_world().payload
    job = Job(title=BANDITS, place=START, open=True)
    the_campaign(world.campaign).jobs = [job]

    _ = world.move(START, ())
    assert world.visit.job == BANDITS

    _ = world.move(TAVERN, ())
    assert world.visit.job == BANDITS
    assert job.open
    assert world.walked() == ["", BANDITS, BANDITS]


def test_move_off_the_tavern_tags_the_visit_with_a_reopened_job() -> None:
    world = hub_world().payload
    world.visits = [Visit(place=TAVERN), Visit(place=START, job=BANDITS), Visit(place=TAVERN)]
    job = Job(title=BANDITS, place=START)
    campaign = the_campaign(world.campaign)
    campaign.jobs = [job]
    campaign.reopen(job)
    assert world.walked_job() is None

    _ = world.move(START, ())

    assert world.visit.job == BANDITS
    assert world.walked_job() is job


def test_walked_job_reads_the_last_visits_tag() -> None:
    world = hub_world().payload
    job = Job(title=BANDITS, place=START, open=True)
    the_campaign(world.campaign).jobs = [job]
    assert world.walked_job() is None

    world.visits.append(Visit(place=START, job=BANDITS))
    assert world.walked_job() is job

    world.visits.append(Visit(place=HALL))
    assert world.walked_job() is None


def test_a_closed_job_still_walked_by_the_last_visit_is_refused() -> None:
    draft = hub_world().draft()
    world = draft.payload
    world.visits = [Visit(place=TAVERN), Visit(place=START, job=BANDITS)]
    the_campaign(world.campaign).jobs = [Job(title=BANDITS, place=START)]
    with pytest.raises(Refusal, match="is not open"):
        _ = draft.commit()


def test_a_visit_taking_a_job_at_the_tavern_is_refused() -> None:
    draft = hub_world().draft()
    world = draft.payload
    world.visits = [Visit(place=TAVERN), Visit(place=START), Visit(place=TAVERN, job=BANDITS)]
    the_campaign(world.campaign).jobs = [Job(title=BANDITS, place=START, open=True)]
    with pytest.raises(Refusal, match="takes 'Bandits' at the hub"):
        _ = draft.commit()


def _mid_job_visits() -> list[Visit]:
    return [
        Visit(place=TAVERN),
        Visit(place=START, job=BANDITS),
        Visit(place=HALL, job=BANDITS),
        Visit(place=START, job=BANDITS),
        Visit(place=TAVERN, job=BANDITS),
    ]


def test_walked_places_leaves_out_the_current_visit_and_lists_a_place_once() -> None:
    world = hub_world().payload
    world.visits = _mid_job_visits()
    the_campaign(world.campaign).jobs = [Job(title=BANDITS, place=START, open=True)]

    assert world.walked_places() == (START, HALL)


def test_apply_return_clears_the_tavern_visits_tag_and_lands_recaps_on_the_span() -> None:
    world = hub_world().payload
    world.visits = _mid_job_visits()
    campaign = the_campaign(world.campaign)
    job = Job(title=BANDITS, place=START, open=True)
    campaign.jobs = [job]
    recaps = {START: "S" * 60, HALL: "H" * 60}

    closed = world.apply_return(debrief="d", summary="s", recaps=recaps, offers=campaign.board)

    assert closed is job
    assert not job.open
    assert world.walked() == ["", BANDITS, BANDITS, BANDITS, ""]
    assert world.walked_job() is None
    assert [visit.recap for visit in world.visits] == ["", "", recaps[HALL], recaps[START], ""]


def _region() -> Dungeon[Npc]:
    return Dungeon[Npc](
        places={
            NEW_SITE: Place(id=NEW_SITE, name="New Site", brief="b", known=False, description="d")
        }
    )


def test_apply_extension_reopens_a_left_open_job_at_its_own_start() -> None:
    world = hub_world(with_map=False).payload
    world.places[OLD_SITE] = Place(
        id=OLD_SITE, name="Old Site", brief="b", known=True, description="d"
    )
    world.add_way(TAVERN, OLD_SITE, known=True)
    world.visits = [
        Visit(place=TAVERN),
        Visit(place=OLD_SITE, job="Crates off Deck 9"),
        Visit(place=TAVERN),
    ]
    old_job = Job(title="Crates off Deck 9", place=OLD_SITE)
    the_campaign(world.campaign).jobs = [old_job]

    anchor = world.apply_extension(_region(), NEW_SITE, reopening=old_job)

    assert anchor.id == OLD_SITE
    way = world.way(OLD_SITE, NEW_SITE)
    assert way is not None and way.known
    campaign = the_campaign(world.campaign)
    assert campaign.jobs[-1] is old_job
    assert old_job.open
    assert world.visit.job == ""
    assert world.walked_job() is None


def test_apply_extension_at_the_tavern_swaps_out_an_unwalked_job() -> None:
    never_walked = hub_world(with_map=False).payload
    campaign = the_campaign(never_walked.campaign)
    campaign.jobs = [Job(title=BANDITS, place=START, open=True)]

    _ = never_walked.apply_extension(_region(), NEW_SITE)

    assert [job.title for job in campaign.jobs] == ["New Site"]
    assert campaign.jobs[-1].open

    walked_before = hub_world().payload
    walked_before.visits = [
        Visit(place=TAVERN),
        Visit(place=START, job=BANDITS),
        Visit(place=TAVERN),
    ]
    campaign = the_campaign(walked_before.campaign)
    old_job = Job(title=BANDITS, place=START, open=True)  # reopened at the board, not walked
    campaign.jobs = [old_job]

    _ = walked_before.apply_extension(_region(), NEW_SITE)

    assert [job.title for job in campaign.jobs] == [BANDITS, "New Site"]
    assert not old_job.open
    assert walked_before.visits[1].job == BANDITS


def test_apply_return_refuses_with_no_job_walked() -> None:
    world = hub_world().payload
    board = the_campaign(world.campaign).board

    with pytest.raises(Refusal, match="no job is open to report"):
        _ = world.apply_return(debrief="d", summary="s", recaps={}, offers=board)


def test_the_map_so_far_names_who_stands_where_and_every_id_in_use() -> None:
    state = small_world()

    shown = state.payload.map_so_far()

    assert "  here: Mira[mira] (met), Lantern[lantern] (met)" in shown
    assert "Robo Mantis" not in shown
    assert shown.endswith(
        "ids in use: crypt, hall, key, lantern, mantis, mira, rope, start, torch, vault"
    )
