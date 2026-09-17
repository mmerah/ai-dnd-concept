import pytest
from pydantic import BaseModel, ValidationError
from support.table import TUNNELGOONS, game, narrowed
from support.tunnelgoons import ENGINE, small_world

from aidm.core.entities import Refusal
from aidm.core.model import Check, ScenarioMeta
from aidm.engines.base import PLAYER_ID, Gauge
from aidm.engines.rooms.engine import MORE_MAP
from aidm.engines.rooms.world import MapDraft, Place, Prop, RegionDraft, Way
from aidm.engines.rooms.worldsmith import check_extension, check_map
from aidm.engines.tunnelgoons.world import Npc, TunnelGoonsGame
from aidm.engines.tunnelgoons.worldsmith import AUTHORING, AbilitiesDraft

ONLY = "only"
HIDDEN = "hidden"
FAR_HALL = "far-hall"
FAR_VAULT = "far-vault"
FAR_ITEM = "far-item"
HALL = "hall"

THIN = MapDraft[Npc](
    places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
    start=ONLY,
)


def _tunnelgoons_game() -> TunnelGoonsGame:
    _, state = game(TUNNELGOONS)
    return narrowed(state, TunnelGoonsGame)


def _region() -> RegionDraft[Npc]:
    return RegionDraft[Npc](
        places={
            FAR_HALL: Place(id=FAR_HALL, name="Far Hall", brief="b", known=False, description="d"),
            FAR_VAULT: Place(
                id=FAR_VAULT, name="Far Vault", brief="b", known=False, description="d"
            ),
        },
        ways={FAR_HALL: [Way(to=FAR_VAULT)]},
        items={FAR_ITEM: Prop(id=FAR_ITEM, name="Far Item", brief="b", known=False, on=FAR_HALL)},
        start=FAR_HALL,
        recap="They pushed past the hall and found the vault beyond it.",
    )


def _wide_region() -> MapDraft[Npc]:
    canon = _tunnelgoons_game().payload
    return MapDraft[Npc](
        places=canon.places,
        ways=canon.ways,
        npcs=canon.npcs,
        items=canon.items,
        start=canon.current.id,
    )


def test_a_one_place_map_with_no_ways_passes_the_map_bar_and_builds() -> None:
    check_map(THIN)

    built = ENGINE.build_scenario(
        ScenarioMeta(title="Only", premise="", scope="One room, one visit."),
        ("srd",),
        THIN,
        "source",
        "d",
    )

    assert built.payload.start == ONLY


def test_an_extension_of_one_hidden_place_with_no_ways_installs_hidden() -> None:
    draft = _tunnelgoons_game().draft()
    extension = RegionDraft[Npc](
        places={HIDDEN: Place(id=HIDDEN, name="Hidden", brief="b", known=False, description="d")},
        start=HIDDEN,
        recap="They found a hidden way and pushed through it.",
    )
    check_extension(extension, draft.payload)

    ENGINE.install(draft, extension)

    assert not draft.payload.places[HIDDEN].known
    assert draft.payload.way(draft.payload.current.id, HIDDEN) is not None


def test_the_shipped_scenario_passes_the_map_bar() -> None:
    check_map(_wide_region())


def test_check_map_refuses_a_dead_npc() -> None:
    corpse = Npc(
        id="corpse",
        name="Corpse",
        brief="",
        place=ONLY,
        known=True,
        alive=False,
        hp=Gauge(current=4, maximum=4),
    )
    draft = MapDraft[Npc](
        places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
        npcs={corpse.id: corpse},
        start=ONLY,
    )
    with pytest.raises(Refusal, match="alive"):
        check_map(draft)


def test_check_map_refuses_an_npc_at_zero_hp() -> None:
    fallen = Npc(
        id="fallen",
        name="Fallen",
        brief="",
        place=ONLY,
        known=True,
        hp=Gauge(current=0, maximum=4),
    )
    draft = MapDraft[Npc](
        places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
        npcs={fallen.id: fallen},
        start=ONLY,
    )
    with pytest.raises(Refusal, match="health above zero"):
        check_map(draft)


def test_check_extension_refuses_an_item_planted_on_the_player() -> None:
    world = _tunnelgoons_game().payload
    extension = RegionDraft[Npc](
        places={HIDDEN: Place(id=HIDDEN, name="Hidden", brief="b", known=False, description="d")},
        items={"planted": Prop(id="planted", name="Planted", brief="b", known=True, on=PLAYER_ID)},
        start=HIDDEN,
        recap="A hand slipped something into their pocket.",
    )
    with pytest.raises(Refusal, match="planted on the player"):
        check_extension(extension, world)


def test_check_extension_refuses_a_place_naming_an_unknown_thing_elsewhere() -> None:
    extension = _region()
    extension.items["far-item-2"] = Prop(
        id="far-item-2", name="Far Item Two", brief="b", known=False, on=FAR_VAULT
    )
    extension.places[FAR_HALL].description = "Far Item Two lies beyond."
    with pytest.raises(Refusal, match="do not name"):
        check_extension(extension, _tunnelgoons_game().payload)


def test_check_extension_accepts_an_unknown_place_naming_itself() -> None:
    extension = _region()
    extension.places[FAR_HALL].description = "Far Hall is a ruin."
    check_extension(extension, _tunnelgoons_game().payload)


def _hiding_gremlin(place_id: str, *, known: bool, brief: str, description: str) -> MapDraft[Npc]:
    gremlin = Npc(
        id="gremlin",
        name="Gremlin",
        brief="",
        place=place_id,
        known=False,
        hp=Gauge(current=4, maximum=4),
    )
    place = Place(
        id=place_id, name=place_id.title(), brief=brief, known=known, description=description
    )
    return MapDraft[Npc](places={place_id: place}, npcs={gremlin.id: gremlin}, start=place_id)


def test_check_map_refuses_a_start_description_naming_a_hidden_dweller() -> None:
    draft = _hiding_gremlin(
        ONLY, known=True, brief="b", description="A Gremlin hides in the shadows."
    )
    with pytest.raises(Refusal, match="do not name"):
        check_map(draft)


def test_an_extension_hiding_a_dweller_named_in_brief_is_refused() -> None:
    world = _tunnelgoons_game().payload
    extension = _hiding_gremlin(
        HIDDEN, known=False, brief="A Gremlin waits in the dark.", description="d"
    )
    with pytest.raises(Refusal, match="do not name"):
        check_extension(extension, world)


def test_check_map_refuses_a_known_dwellers_brief_naming_a_hidden_dweller() -> None:
    gremlin = Npc(
        id="gremlin",
        name="Gremlin",
        brief="",
        place=ONLY,
        known=False,
        hp=Gauge(current=4, maximum=4),
    )
    sentry = Npc(
        id="sentry",
        name="Sentry",
        brief="He watches for the Gremlin.",
        place=ONLY,
        known=True,
        hp=Gauge(current=4, maximum=4),
    )
    draft = MapDraft[Npc](
        places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
        npcs={gremlin.id: gremlin, sentry.id: sentry},
        start=ONLY,
    )
    with pytest.raises(Refusal, match="do not name"):
        check_map(draft)


def test_check_map_refuses_a_hidden_dwellers_own_brief_naming_another_hidden_dweller() -> None:
    """The leak a later `reveal` would make must be caught while both are still hidden."""
    gremlin = Npc(
        id="gremlin",
        name="Gremlin",
        brief="",
        place=ONLY,
        known=False,
        hp=Gauge(current=4, maximum=4),
    )
    sentry = Npc(
        id="sentry",
        name="Sentry",
        brief="He watches for the Gremlin.",
        place=ONLY,
        known=False,
        hp=Gauge(current=4, maximum=4),
    )
    draft = MapDraft[Npc](
        places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
        npcs={gremlin.id: gremlin, sentry.id: sentry},
        start=ONLY,
    )
    with pytest.raises(Refusal, match="do not name"):
        check_map(draft)


def test_check_map_refuses_an_item_on_the_player_naming_a_hidden_dweller() -> None:
    gremlin = Npc(
        id="gremlin",
        name="Gremlin",
        brief="",
        place=ONLY,
        known=False,
        hp=Gauge(current=4, maximum=4),
    )
    charm = Prop(
        id="charm", name="Charm", brief="A ward against the Gremlin.", known=True, on=PLAYER_ID
    )
    draft = MapDraft[Npc](
        places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
        npcs={gremlin.id: gremlin},
        items={charm.id: charm},
        start=ONLY,
    )
    with pytest.raises(Refusal, match="do not name"):
        check_map(draft)


def test_attach_joins_at_the_current_place_and_the_world_validates() -> None:
    state = small_world()
    world = state.payload
    anchor = world.current.id

    region = _region()
    world.attach(region, region.start)

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

    with pytest.raises(Refusal, match="not already in the world"):
        check_extension(reused, state.payload)


def test_more_map_is_offered_only_once_every_place_is_known() -> None:
    state = small_world()
    assert ENGINE.player_view(state).action is None

    draft = state.draft()
    for place in draft.payload.places.values():
        place.known = True
    assert ENGINE.player_view(draft.commit()).action == MORE_MAP


def test_install_on_a_game_from_the_engine() -> None:
    draft = _tunnelgoons_game().draft()
    anchor = draft.payload.current.id

    ENGINE.install(draft, _region())

    assert FAR_HALL in draft.payload.places
    assert draft.payload.way(anchor, FAR_HALL) is not None


def test_attach_appends_unknown_ways_both_directions() -> None:
    state = small_world()
    world = state.payload
    anchor = world.current.id
    region = _region()

    world.attach(region, region.start)

    out = world.way(anchor, FAR_HALL)
    back = world.way(FAR_HALL, anchor)
    assert out is not None and not out.known
    assert back is not None and not back.known


async def test_write_next_asks_for_the_map_draft() -> None:
    recorded: list[type[BaseModel]] = []
    prompts: list[str] = []

    async def answer[M: BaseModel](prompt: str, model: type[M], _check: Check[M]) -> M:
        recorded.append(model)
        prompts.append(prompt)
        return model.model_validate({**THIN.model_dump(), "recap": "They pushed north."})

    _ = await ENGINE.write_next(small_world(), "Push north.", answer)

    assert recorded == [RegionDraft[Npc]]
    # The `hp` rule reaches the worldsmith only through the engine's guidance.
    assert AUTHORING in prompts[0]


async def test_write_next_prompt_carries_scenes_so_far() -> None:
    prompts: list[str] = []

    async def answer[M: BaseModel](prompt: str, model: type[M], _check: Check[M]) -> M:
        prompts.append(prompt)
        return model.model_validate({**THIN.model_dump(), "recap": "They nosed around the docks."})

    _ = await ENGINE.write_next(small_world(), "Nose around the docks.", answer)

    assert "SCENES SO FAR" in prompts[0]


def test_abilities_draft_refuses_a_wrong_point_total() -> None:
    with pytest.raises(ValidationError, match="share exactly 3 points"):
        AbilitiesDraft(abilities={"brute": 2, "skulker": 2, "erudite": 0})
