from collections.abc import Callable

import pytest
from pydantic import BaseModel
from support.table import TUNNELGOONS, game, the_campaign
from support.tunnelgoons import MIRA, START, TAVERN, hub_world, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.core.play import Commission
from aidm.engines.base import Counter
from aidm.engines.hub import Attempt, Job, Offer
from aidm.engines.rooms.drafts import ItemDraft, MapDraft, NpcDraft, ReturnDraft
from aidm.engines.rooms.engine import REPORT_IN
from aidm.engines.rooms.world import Item, Place, Visit, Way
from aidm.engines.rooms.worldsmith import (
    extension_refusal,
    hub_refusal,
    item_refusal,
    job_refusal,
    map_refusal,
    npc_refusal,
    return_refusal,
)
from aidm.engines.tunnelgoons.engine import TunnelGoonsEngine
from aidm.engines.tunnelgoons.world import Npc, TunnelGoonsGame
from aidm.engines.tunnelgoons.worldsmith import AUTHORING

ENGINE = TunnelGoonsEngine()

ONLY = EntityId("only")
FAR_HALL = EntityId("far-hall")
FAR_VAULT = EntityId("far-vault")
FAR_ITEM = EntityId("far-item")
HALL = EntityId("hall")

THIN = MapDraft[Npc](
    places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
    start=ONLY,
)


def _tunnelgoons_game() -> TunnelGoonsGame:
    _, state = game(TUNNELGOONS)
    if not isinstance(state, TunnelGoonsGame):
        raise AssertionError("the Tunnel Goons engine began another game type")
    return state


def _region() -> MapDraft[Npc]:
    return MapDraft[Npc](
        places={
            FAR_HALL: Place(id=FAR_HALL, name="Far Hall", brief="b", known=False, description="d"),
            FAR_VAULT: Place(
                id=FAR_VAULT, name="Far Vault", brief="b", known=False, description="d"
            ),
        },
        ways={FAR_HALL: [Way(to=FAR_VAULT)]},
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
    canon = _tunnelgoons_game().payload
    draft = MapDraft[Npc](
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.current.id,
    )
    assert map_refusal(draft) is None


def test_attach_joins_at_the_current_place_and_the_world_validates() -> None:
    state = small_world()
    world = state.payload
    anchor = world.current.id

    region = _region()
    world.attach(region, region.start, known=False)

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
            "ways": {HALL: [Way(to=FAR_VAULT)]},
            "start": HALL,
        }
    )

    refused = extension_refusal(reused, state.payload)
    assert refused is not None
    assert "not already in the world" in refused


def test_way_open_is_false_on_the_shipped_map_and_true_once_every_place_is_known() -> None:
    state = small_world()
    assert not ENGINE.ready(state)

    draft = state.draft()
    for place in draft.payload.places.values():
        place.known = True
    assert ENGINE.ready(draft.commit())


def test_install_extension_on_a_game_from_the_engine() -> None:
    draft = _tunnelgoons_game().draft()
    anchor = draft.payload.current.id

    facts = ENGINE.install_extension(draft, _region())

    assert [fact.kind for fact in facts] == ["region_added"]
    assert not facts[0].told
    assert FAR_HALL in draft.payload.places
    assert draft.payload.way(anchor, FAR_HALL) is not None


RETURN = ReturnDraft(
    debrief="The crates are cleared and paid for.",
    offers=(Offer(title="Job One", pitch="pitch one"), Offer(title="Job Two", pitch="pitch two")),
    summary=(
        "Kael cleared the vault and squared the debt, though the crypt beyond stayed sealed and "
        "whatever waits down there is still a mystery worth chasing."
    ),
    recaps={
        START: "Kael slipped past Mira's watch, pried the vault open, and carried the take out."
    },
)


def test_way_open_at_the_hub_with_the_map_unwalked_but_not_on_a_one_shot() -> None:
    assert ENGINE.ready(hub_world())
    assert not ENGINE.ready(small_world())


def test_attach_known_appends_known_ways_and_unknown_appends_unknown_both_directions() -> None:
    known_state = small_world()
    known_world = known_state.payload
    anchor = known_world.current.id
    region = _region()
    known_world.attach(region, region.start, known=True)
    out_known = known_world.way(anchor, FAR_HALL)
    in_known = known_world.way(FAR_HALL, anchor)
    assert out_known is not None and out_known.known
    assert in_known is not None and in_known.known

    unknown_state = small_world()
    unknown_world = unknown_state.payload
    unknown_world.attach(region, region.start, known=False)
    out_unknown = unknown_world.way(anchor, FAR_HALL)
    in_unknown = unknown_world.way(FAR_HALL, anchor)
    assert out_unknown is not None and not out_unknown.known
    assert in_unknown is not None and not in_unknown.known


def _walked_job_visits() -> list[Visit]:
    return [
        Visit(place=TAVERN),
        Visit(place=START),
        Visit(place=TAVERN),
    ]


async def test_write_extension_picks_return_draft_on_report_in_with_a_job_open() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [
        Job(title="Bandits", place=START, attempts=[Attempt(started=1)])
    ]
    recorded: list[type[BaseModel]] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        recorded.append(model)
        answer = model.model_validate(RETURN.model_dump())
        assert refusal(answer) is None
        return answer

    _ = await ENGINE.write_extension(state, REPORT_IN, answer)

    assert recorded == [ReturnDraft]


async def test_write_extension_return_prompt_carries_hub_sections_and_reads_report_in() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [
        Job(title="Bandits", place=START, attempts=[Attempt(started=1)])
    ]
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        answer = model.model_validate(RETURN.model_dump())
        assert refusal(answer) is None
        return answer

    _ = await ENGINE.write_extension(state, REPORT_IN, answer)

    assert "THIS JOB" in prompts[0]
    assert "THE VERDICT" in prompts[0]
    assert "ENGINE GUIDANCE" in prompts[0]
    assert "WHAT COMES NEXT:\nReport in." in prompts[0]


async def test_write_extension_refuses_report_in_with_no_job_open() -> None:
    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        raise AssertionError("no answer should be asked for")

    unwalked = hub_world()
    with pytest.raises(Refusal, match="no job is open to report"):
        _ = await ENGINE.write_extension(unwalked, REPORT_IN, answer)

    stamped_not_walked = hub_world()
    the_campaign(stamped_not_walked.payload.campaign).jobs = [
        Job(title="Bandits", place=START, attempts=[Attempt()])
    ]
    with pytest.raises(Refusal, match="no job is open to report"):
        _ = await ENGINE.write_extension(stamped_not_walked, REPORT_IN, answer)


async def test_write_extension_refuses_a_walked_job_open_with_another_intent() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [
        Job(title="Bandits", place=START, attempts=[Attempt(started=1)])
    ]

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        raise AssertionError("no answer should be asked for")

    with pytest.raises(Refusal, match="report the open job first"):
        _ = await ENGINE.write_extension(state, "Nose around the docks.", answer)


async def test_write_extension_asks_for_map_draft_away_or_at_the_hub_otherwise() -> None:
    recorded: list[type[BaseModel]] = []
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        recorded.append(model)
        prompts.append(prompt)
        return model.model_validate(THIN.model_dump())

    _ = await ENGINE.write_extension(hub_world(), "Nose around the docks.", answer)
    _ = await ENGINE.write_extension(small_world(), "Push north.", answer)

    assert recorded == [MapDraft[Npc], MapDraft[Npc]]
    # The `hp` rule reaches the worldsmith only through the engine's guidance.
    assert all(AUTHORING in prompt for prompt in prompts)


def _job_walking() -> Job:
    return Job(title="Bandits", place=START, attempts=[Attempt(started=1)])


def test_return_refusal_names_a_walked_place_missing_its_recap() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [_job_walking()]

    refused = return_refusal(RETURN.model_copy(update={"recaps": {}}), state.payload)

    assert refused is not None
    assert START in refused


def test_return_refusal_names_a_recap_for_a_place_not_walked() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [_job_walking()]
    extra = RETURN.model_copy(update={"recaps": {**RETURN.recaps, HALL: "H" * 60}})

    refused = return_refusal(extra, state.payload)

    assert refused is not None
    assert HALL in refused


def test_return_refusal_refuses_a_recap_of_the_current_tavern_visit() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [_job_walking()]
    with_tavern = RETURN.model_copy(update={"recaps": {**RETURN.recaps, TAVERN: "T" * 60}})

    refused = return_refusal(with_tavern, state.payload)

    assert refused is not None
    assert TAVERN in refused


def test_return_refusal_refuses_a_debrief_naming_an_unmet_npc() -> None:
    state = hub_world()
    state.payload.visits = _walked_job_visits()
    the_campaign(state.payload.campaign).jobs = [_job_walking()]
    naming = RETURN.model_copy(update={"debrief": "Robo Mantis clicked in the dark the whole way."})

    refused = return_refusal(naming, state.payload)

    assert refused is not None
    assert "Robo Mantis" in refused


def test_install_extension_on_a_return_draft_closes_the_job() -> None:
    state = hub_world()
    world = state.payload
    world.visits = _walked_job_visits()
    campaign = the_campaign(world.campaign)
    campaign.jobs = [
        Job(title="Bandits", place=START, finished=True, attempts=[Attempt(started=1)])
    ]

    facts = ENGINE.install_extension(state, RETURN)

    assert campaign.jobs[-1].debrief == RETURN.debrief
    assert campaign.jobs[-1].finished
    assert campaign.board == RETURN.offers
    assert [fact.kind for fact in facts] == ["job_closed"]
    assert facts[0].told
    assert facts[0].card.startswith("Job done: Bandits")


def test_install_extension_on_a_map_draft_at_the_hub_takes_the_job() -> None:
    state = hub_world(with_map=False)
    world = state.payload
    canon = _tunnelgoons_game().payload
    extension = MapDraft[Npc](
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.current.id,
    )

    facts = ENGINE.install_extension(state, extension)

    start_name = extension.places[extension.start].name
    assert [fact.kind for fact in facts] == ["job_taken"]
    assert facts[0].told
    assert facts[0].card == f"A way opens: {start_name}"
    way = world.way(TAVERN, extension.start)
    assert way is not None
    assert way.known
    assert the_campaign(world.campaign).jobs[-1] == Job(
        title=start_name, place=extension.start, attempts=[Attempt()]
    )


def test_install_extension_on_a_return_draft_lands_recaps_on_each_places_last_visit() -> None:
    state = hub_world()
    world = state.payload
    world.visits = [
        Visit(place=TAVERN),
        Visit(place=START),
        Visit(place=HALL),
        Visit(place=START),
        Visit(place=TAVERN),
    ]
    the_campaign(world.campaign).jobs = [_job_walking()]
    recapped = RETURN.model_copy(update={"recaps": {START: "S" * 60, HALL: "H" * 60}})

    facts = ENGINE.install_extension(state, recapped)

    assert world.visits[1].recap == ""
    assert world.visits[2].recap == recapped.recaps[HALL]
    assert world.visits[3].recap == recapped.recaps[START]
    assert [fact.kind for fact in facts] == ["job_closed"]


OLD_SITE = EntityId("old-site")


def _left_open_job_world() -> tuple[TunnelGoonsGame, Job]:
    state = hub_world(with_map=False)
    world = state.payload
    world.places[OLD_SITE] = Place(
        id=OLD_SITE, name="Old Site", brief="b", known=True, description="d"
    )
    world.add_way(TAVERN, OLD_SITE, known=True)
    world.visits = [Visit(place=TAVERN), Visit(place=OLD_SITE), Visit(place=TAVERN)]
    old_job = Job(
        title="Crates off Deck 9",
        place=OLD_SITE,
        debrief="left off mid-count",
        attempts=[Attempt(started=1, returned=2)],
    )
    the_campaign(world.campaign).jobs = [old_job]
    return state, old_job


def _wide_region() -> MapDraft[Npc]:
    canon = _tunnelgoons_game().payload
    return MapDraft[Npc](
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.current.id,
    )


def test_install_extension_reopens_a_left_open_job_at_its_own_start() -> None:
    state, old_job = _left_open_job_world()
    world = state.payload
    campaign = the_campaign(world.campaign)
    reopening = campaign.taken('I take the job "Crates off Deck 9".')
    assert reopening is old_job

    extension = _wide_region()
    facts = ENGINE.install_extension(state, extension, reopening=reopening)

    assert facts[0].kind == "job_taken"
    assert "Old Site" in facts[0].trace
    assert "Tavern" not in facts[0].trace
    way = world.way(OLD_SITE, extension.start)
    assert way is not None and way.known
    assert campaign.jobs[-1] is old_job
    assert campaign.jobs[-1].open
    assert campaign.jobs[-1].attempts[-1].started is None
    assert len(campaign.jobs[-1].attempts) == 2


def test_swapping_out_a_reopened_unwalked_job_leaves_it_closed_not_open() -> None:
    state, old_job = _left_open_job_world()
    world = state.payload
    campaign = the_campaign(world.campaign)
    reopening = campaign.taken('I take the job "Crates off Deck 9".')
    _ = ENGINE.install_extension(state, _wide_region(), reopening=reopening)

    campaign.swap_out()

    assert old_job in campaign.jobs
    assert not old_job.open
    assert old_job.attempts[-1].returned == 2


async def test_write_extension_prompt_carries_scenes_so_far() -> None:
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        return model.model_validate(THIN.model_dump())

    _ = await ENGINE.write_extension(hub_world(), "Nose around the docks.", answer)

    assert "SCENES SO FAR" in prompts[0]


async def test_write_extension_prompt_carries_the_job_before_only_on_a_retake() -> None:
    state, old_job = _left_open_job_world()
    campaign = the_campaign(state.payload.campaign)
    retake = 'I take the job "Crates off Deck 9".'
    reopening = campaign.taken(retake)
    assert reopening is old_job
    prompts: list[str] = []

    async def answer[M: BaseModel](
        prompt: str, model: type[M], refusal: Callable[[M], str | None]
    ) -> M:
        prompts.append(prompt)
        return model.model_validate(THIN.model_dump())

    _ = await ENGINE.write_extension(state, retake, answer, reopening=reopening)
    _ = await ENGINE.write_extension(state, "Nose around the docks.", answer, reopening=None)

    assert "THE JOB BEFORE" in prompts[0]
    assert "THE JOB BEFORE" not in prompts[1]


def test_hub_refusal_needs_a_two_or_three_offer_board_and_passes_the_shipped_campaign() -> None:
    thin_board = THIN.model_copy(update={"board": None})
    refused = hub_refusal(thin_board)
    assert refused is not None
    assert "two or three offers" in refused

    _, campaign_state = game(TUNNELGOONS, "campaign")
    if not isinstance(campaign_state, TunnelGoonsGame):
        raise AssertionError("the Tunnel Goons engine began another game type")
    canon = campaign_state.payload
    draft = MapDraft[Npc](
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.current.id,
        board=the_campaign(canon.campaign).board,
    )
    assert hub_refusal(draft) is None


def test_map_refusal_refuses_a_one_shot_draft_carrying_a_board() -> None:
    with_board = THIN.model_copy(
        update={"board": (Offer(title="Only", pitch="p"), Offer(title="Other", pitch="p2"))}
    )
    refused = map_refusal(with_board)
    assert refused is not None
    assert "no `board`" in refused


def test_opening_canon_refuses_a_campaign_draft_without_a_board() -> None:
    with pytest.raises(Refusal, match="needs a board"):
        ENGINE.opening_canon(_region(), "source", "campaign")


def _npc(entity_id: EntityId, *, place: EntityId, known: bool = False) -> Npc:
    return Npc(
        id=entity_id,
        name="L",
        brief="b",
        known=known,
        place=place,
        hp=Counter(current=4, maximum=4),
    )


def test_install_commission_writes_an_npc_at_the_current_place_unmet() -> None:
    state = small_world()
    world = state.payload
    asked = Commission(kind="npc", brief="a lookout at the door")
    state.commissions.append(asked)
    lookout = _npc(EntityId("lookout"), place=world.current.id)
    assert npc_refusal(NpcDraft[Npc](npc=lookout), world) is None

    facts = ENGINE.install_commission(state, asked, NpcDraft[Npc](npc=lookout))

    assert world.npcs[lookout.id].place == world.current.id
    assert not world.npcs[lookout.id].known
    assert asked not in state.commissions
    assert [fact.kind for fact in facts] == ["commissioned"]


def test_install_commission_writes_an_item_on_the_place_or_a_living_npc_there() -> None:
    state = small_world()
    world = state.payload

    on_place = Commission(kind="item", brief="a coin purse in the dust")
    state.commissions.append(on_place)
    purse = Item(id=EntityId("purse"), name="Purse", brief="b", known=False, on=world.current.id)
    ENGINE.install_commission(state, on_place, ItemDraft(item=purse))
    assert world.items[purse.id].on == world.current.id

    on_npc = Commission(kind="item", brief="a ring on Mira's hand")
    state.commissions.append(on_npc)
    ring = Item(id=EntityId("ring"), name="Ring", brief="b", known=False, on=MIRA)
    assert item_refusal(ItemDraft(item=ring), world) is None
    ENGINE.install_commission(state, on_npc, ItemDraft(item=ring))
    assert world.items[ring.id].on == MIRA


def test_install_commission_attaches_a_region_hidden() -> None:
    state = small_world()
    world = state.payload
    asked = Commission(kind="region", brief="a passage beyond the crypt")
    state.commissions.append(asked)
    region = _region()

    facts = ENGINE.install_commission(state, asked, region)

    assert not world.places[FAR_HALL].known
    way = world.way(world.current.id, FAR_HALL)
    assert way is not None and not way.known
    assert asked not in state.commissions
    assert [fact.kind for fact in facts] == ["commissioned"]


def test_npc_refusal_refuses_a_wrong_place_a_used_id_and_a_known_entry() -> None:
    world = small_world().payload

    wrong_place = NpcDraft[Npc](npc=_npc(EntityId("lookout"), place=HALL))
    refused = npc_refusal(wrong_place, world)
    assert refused is not None and world.current.id in refused

    reused_id = NpcDraft[Npc](npc=_npc(MIRA, place=world.current.id))
    refused = npc_refusal(reused_id, world)
    assert refused is not None and "a new id" in refused

    known = NpcDraft[Npc](npc=_npc(EntityId("lookout"), place=world.current.id, known=True))
    refused = npc_refusal(known, world)
    assert refused is not None and "unmet" in refused


def test_item_refusal_refuses_an_on_that_is_neither_the_place_nor_a_living_npc_here() -> None:
    world = small_world().payload
    elsewhere = ItemDraft(
        item=Item(id=EntityId("coin"), name="Coin", brief="b", known=False, on=HALL)
    )

    refused = item_refusal(elsewhere, world)

    assert refused is not None
    assert "living npc" in refused


def test_job_refusal_needs_a_later_npc_commission_met_by_a_new_npc() -> None:
    world = hub_world(with_map=False).payload
    asked = [Commission(kind="npc", brief="a fence for stolen goods", later=True)]
    empty = _wide_region().model_copy(update={"npcs": {}})

    refused = job_refusal(empty, world, asked)
    assert refused is not None
    assert "1 npcs asked for, 0 written" in refused

    written = empty.model_copy(
        update={"npcs": {EntityId("fence"): _npc(EntityId("fence"), place=empty.start)}}
    )
    assert job_refusal(written, world, asked) is None


async def test_a_later_commission_survives_return_and_clears_on_the_job_that_meets_it() -> None:
    state = hub_world(with_map=False)
    world = state.payload
    world.visits = _walked_job_visits()
    the_campaign(world.campaign).jobs = [
        Job(title="Bandits", place=START, finished=True, attempts=[Attempt(started=1)])
    ]
    asked = Commission(kind="npc", brief="a fence for stolen goods", later=True)
    state.commissions.append(asked)

    ENGINE.install_extension(state, RETURN)
    assert asked in state.commissions

    met = _wide_region().model_copy(
        update={"npcs": {EntityId("fence"): _npc(EntityId("fence"), place=_wide_region().start)}}
    )
    ENGINE.install_extension(state, met)

    assert asked not in state.commissions
