import pytest
from core_test_support import TUNNELGOONS, game
from pydantic import BaseModel
from tunnelgoons_test_support import START, TAVERN, hub_world, small_world

from aidm.core.entities import EntityId
from aidm.core.model import CheckAnswer
from aidm.engines.hub import Debrief, Offer
from aidm.engines.tunnelgoons.views import REPORT_IN
from aidm.engines.tunnelgoons.world import Item, Place, TunnelGoonsGame, Visit, Way
from aidm.engines.tunnelgoons.worldsmith import (
    MapDraft,
    ReturnDraft,
    attach,
    extension_refusal,
    hub_refusal,
    install_extension,
    map_refusal,
    way_open,
    write_extension,
)

ONLY = EntityId("only")
FAR_HALL = EntityId("far-hall")
FAR_VAULT = EntityId("far-vault")
FAR_ITEM = EntityId("far-item")
HALL = EntityId("hall")

THIN = MapDraft(
    places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
    start=ONLY,
)


def _tunnelgoons_game() -> TunnelGoonsGame:
    _, state = game(TUNNELGOONS)
    if not isinstance(state, TunnelGoonsGame):
        raise AssertionError("the Tunnel Goons engine began another game type")
    return state


def _region() -> MapDraft:
    return MapDraft(
        places={
            FAR_HALL: Place(id=FAR_HALL, name="Far Hall", brief="b", known=False, description="d"),
            FAR_VAULT: Place(
                id=FAR_VAULT, name="Far Vault", brief="b", known=False, description="d"
            ),
        },
        ways={FAR_HALL: (Way(to=FAR_VAULT),)},
        items={FAR_ITEM: Item(id=FAR_ITEM, name="Far Item", brief="b", known=False, on=FAR_HALL)},
        start=FAR_HALL,
    )


def test_the_map_bar_names_each_missing_thing_on_a_thin_draft() -> None:
    refused = map_refusal(THIN)
    assert refused is not None
    assert "4 or more places" in refused
    assert "at least one way starting unknown" in refused
    assert "at least one way starting locked" in refused
    assert "at least one hidden npc or item" in refused
    assert "a shortcut" in refused


def test_the_shipped_scenario_passes_the_map_bar() -> None:
    canon = _tunnelgoons_game().payload.world
    draft = MapDraft(
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.player.place,
    )
    assert map_refusal(draft) is None


def test_attach_joins_at_the_current_place_and_the_world_validates() -> None:
    state = small_world()
    world = state.payload.world
    anchor = world.player.place

    attach(world, _region(), known=False)

    assert FAR_HALL in world.places
    assert FAR_VAULT in world.places
    assert world.way(anchor, FAR_HALL) is not None
    assert world.way(FAR_HALL, anchor) is not None


def test_a_region_reusing_an_id_already_in_the_world_is_refused() -> None:
    state = small_world()
    reused = _region().model_copy(
        update={
            "places": {
                HALL: Place(id=HALL, name="Hall Again", brief="b", known=False, description="d"),
                FAR_VAULT: Place(
                    id=FAR_VAULT, name="Far Vault", brief="b", known=False, description="d"
                ),
            },
            "ways": {HALL: (Way(to=FAR_VAULT),)},
            "start": HALL,
        }
    )

    refused = extension_refusal(reused, state.payload.world)
    assert refused is not None
    assert "not already in the world" in refused


def test_way_open_is_false_on_the_shipped_map_and_true_once_every_place_is_known() -> None:
    state = small_world()
    assert not way_open(state)

    draft = state.draft()
    for place in draft.payload.world.places.values():
        place.known = True
    assert way_open(draft.committed())


def test_install_extension_on_a_game_from_the_engine() -> None:
    draft = _tunnelgoons_game().draft()
    anchor = draft.payload.world.player.place

    facts = install_extension(draft, _region())

    assert [fact.kind for fact in facts] == ["region_added"]
    assert not facts[0].told
    assert FAR_HALL in draft.payload.world.places
    assert draft.payload.world.way(anchor, FAR_HALL) is not None


RETURN = ReturnDraft(
    debrief="The crates are cleared and paid for.",
    offers=(Offer(title="Job One", pitch="pitch one"), Offer(title="Job Two", pitch="pitch two")),
)


def test_way_open_at_the_hub_with_the_map_unwalked_but_not_on_a_one_shot() -> None:
    assert way_open(hub_world())
    assert not way_open(small_world())


def test_attach_known_appends_known_ways_and_unknown_appends_unknown_both_directions() -> None:
    known_state = small_world()
    known_world = known_state.payload.world
    anchor = known_world.player.place
    attach(known_world, _region(), known=True)
    out_known = known_world.way(anchor, FAR_HALL)
    in_known = known_world.way(FAR_HALL, anchor)
    assert out_known is not None and out_known.known
    assert in_known is not None and in_known.known

    unknown_state = small_world()
    unknown_world = unknown_state.payload.world
    attach(unknown_world, _region(), known=False)
    out_unknown = unknown_world.way(anchor, FAR_HALL)
    in_unknown = unknown_world.way(FAR_HALL, anchor)
    assert out_unknown is not None and not out_unknown.known
    assert in_unknown is not None and not in_unknown.known


def _walked_job_visits() -> list[Visit]:
    return [
        Visit(place=TAVERN, job="Bandits"),
        Visit(place=START, job="Bandits"),
        Visit(place=TAVERN, job="Bandits"),
    ]


async def test_write_extension_picks_return_draft_on_report_in_with_a_job_open() -> None:
    state = hub_world()
    state.payload.world.visits = _walked_job_visits()
    recorded: list[type[BaseModel]] = []

    async def answer(_prompt: str, model: type[BaseModel], refusal: CheckAnswer) -> BaseModel:
        recorded.append(model)
        assert refusal(RETURN) is None
        return RETURN

    _ = await write_extension(state, REPORT_IN, answer)

    assert recorded == [ReturnDraft]


async def test_write_extension_refuses_report_in_with_no_job_open() -> None:
    async def answer(_prompt: str, _model: type[BaseModel], _refusal: CheckAnswer) -> BaseModel:
        raise AssertionError("no answer should be asked for")

    unwalked = hub_world()
    with pytest.raises(ValueError, match="no job is open to report"):
        _ = await write_extension(unwalked, REPORT_IN, answer)

    stamped_not_walked = hub_world()
    stamped_not_walked.payload.world.visit.job = "Bandits"
    with pytest.raises(ValueError, match="no job is open to report"):
        _ = await write_extension(stamped_not_walked, REPORT_IN, answer)


async def test_write_extension_refuses_a_walked_job_open_with_another_intent() -> None:
    state = hub_world()
    state.payload.world.visits = _walked_job_visits()

    async def answer(_prompt: str, _model: type[BaseModel], _refusal: CheckAnswer) -> BaseModel:
        raise AssertionError("no answer should be asked for")

    with pytest.raises(ValueError, match="report the open job first"):
        _ = await write_extension(state, "Nose around the docks.", answer)


async def test_write_extension_asks_for_map_draft_away_or_at_the_hub_otherwise() -> None:
    recorded: list[type[BaseModel]] = []

    async def answer(_prompt: str, model: type[BaseModel], _refusal: CheckAnswer) -> BaseModel:
        recorded.append(model)
        return THIN

    _ = await write_extension(hub_world(), "Nose around the docks.", answer)
    _ = await write_extension(small_world(), "Push north.", answer)

    assert recorded == [MapDraft, MapDraft]


def test_install_extension_on_a_return_draft_closes_the_job() -> None:
    state = hub_world()
    world = state.payload.world
    world.visits = _walked_job_visits()
    world.job_done = True

    facts = install_extension(state, RETURN)

    visit = world.visit
    assert visit.debrief == Debrief(text=RETURN.debrief, finished=True)
    assert visit.job == ""
    assert not world.job_done
    assert world.board == RETURN.offers
    assert [fact.kind for fact in facts] == ["job_closed"]
    assert facts[0].told
    assert facts[0].card.startswith("Job done: Bandits")


def test_install_extension_on_a_map_draft_at_the_hub_takes_the_job() -> None:
    state = hub_world(with_map=False)
    world = state.payload.world
    canon = _tunnelgoons_game().payload.world
    written = MapDraft(
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.player.place,
    )

    facts = install_extension(state, written)

    start_name = written.places[written.start].name
    assert [fact.kind for fact in facts] == ["job_taken"]
    assert facts[0].told
    assert facts[0].card == f"A way opens: {start_name}"
    way = world.way(TAVERN, written.start)
    assert way is not None
    assert way.known
    assert world.visit.job == start_name


def test_hub_refusal_needs_a_two_or_three_offer_board_and_passes_the_shipped_campaign() -> None:
    thin_board = THIN.model_copy(update={"board": (Offer(title="Only", pitch="p"),)})
    refused = hub_refusal(thin_board)
    assert refused is not None
    assert "board" in refused

    _, campaign_state = game(TUNNELGOONS, "campaign")
    if not isinstance(campaign_state, TunnelGoonsGame):
        raise AssertionError("the Tunnel Goons engine began another game type")
    canon = campaign_state.payload.world
    draft = MapDraft(
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.player.place,
        board=canon.board,
    )
    assert hub_refusal(draft) is None


def test_map_refusal_refuses_a_one_shot_draft_carrying_a_board() -> None:
    with_board = THIN.model_copy(update={"board": (Offer(title="Only", pitch="p"),)})
    refused = map_refusal(with_board)
    assert refused is not None
    assert "no `board`" in refused
