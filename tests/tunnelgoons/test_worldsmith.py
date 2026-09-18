import pytest
from support.table import TUNNELGOONS, game, narrowed
from support.tunnelgoons import ENGINE, small_world

from aidm.core.entities import Refusal
from aidm.core.model import ScenarioMeta
from aidm.engines.base import PLAYER_ID, Gauge
from aidm.engines.rooms.engine import MORE_MAP
from aidm.engines.rooms.world import MapProposal, Place, Prop, RegionProposal, Way
from aidm.engines.rooms.worldsmith import check_extension, check_map
from aidm.engines.tunnelgoons.world import Goon, TunnelGoonsGame

ONLY = "only"
HIDDEN = "hidden"
FAR_HALL = "far-hall"
FAR_VAULT = "far-vault"
FAR_ITEM = "far-item"
HALL = "hall"

THIN = MapProposal[Goon](
    places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
    start=ONLY,
)


def _tunnelgoons_game() -> TunnelGoonsGame:
    _, state = game(TUNNELGOONS)
    return narrowed(state, TunnelGoonsGame)


def _region() -> RegionProposal[Goon]:
    return RegionProposal[Goon](
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


def _wide_region() -> MapProposal[Goon]:
    canon = _tunnelgoons_game().world
    return MapProposal[Goon](
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
        "srd",
        THIN,
        "source",
        "d",
    )

    assert built.opening.start == ONLY


def test_an_extension_of_one_hidden_place_with_no_ways_installs_hidden() -> None:
    draft = _tunnelgoons_game().draft()
    extension = RegionProposal[Goon](
        places={HIDDEN: Place(id=HIDDEN, name="Hidden", brief="b", known=False, description="d")},
        start=HIDDEN,
        recap="They found a hidden way and pushed through it.",
    )
    check_extension(extension, draft.world)

    ENGINE.install(draft, extension)

    assert not draft.world.places[HIDDEN].known
    assert draft.world.way(draft.world.current.id, HIDDEN) is not None


def test_the_shipped_scenario_passes_the_map_bar() -> None:
    check_map(_wide_region())


def test_check_map_refuses_a_dead_npc() -> None:
    corpse = Goon(
        id="corpse",
        name="Corpse",
        brief="",
        place=ONLY,
        known=True,
        alive=False,
        hp=Gauge(current=4, maximum=4),
    )
    draft = MapProposal[Goon](
        places={ONLY: Place(id=ONLY, name="Only", brief="b", known=True, description="d")},
        npcs={corpse.id: corpse},
        start=ONLY,
    )
    with pytest.raises(Refusal, match="alive"):
        check_map(draft)


def test_check_extension_refuses_an_item_planted_on_the_player() -> None:
    world = _tunnelgoons_game().world
    extension = RegionProposal[Goon](
        places={HIDDEN: Place(id=HIDDEN, name="Hidden", brief="b", known=False, description="d")},
        items={"planted": Prop(id="planted", name="Planted", brief="b", known=True, on=PLAYER_ID)},
        start=HIDDEN,
        recap="A hand slipped something into their pocket.",
    )
    with pytest.raises(Refusal, match="planted on the player"):
        check_extension(extension, world)


def test_check_extension_accepts_an_unknown_place_naming_itself() -> None:
    extension = _region()
    extension.places[FAR_HALL].description = "Far Hall is a ruin."
    check_extension(extension, _tunnelgoons_game().world)


def _hiding_gremlin(
    place_id: str, *, known: bool, brief: str, description: str
) -> MapProposal[Goon]:
    gremlin = Goon(
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
    return MapProposal[Goon](places={place_id: place}, npcs={gremlin.id: gremlin}, start=place_id)


def test_check_map_refuses_a_start_description_naming_a_hidden_dweller() -> None:
    draft = _hiding_gremlin(
        ONLY, known=True, brief="b", description="A Gremlin hides in the shadows."
    )
    with pytest.raises(Refusal, match="do not name"):
        check_map(draft)


def test_attach_joins_at_the_current_place_and_the_world_validates() -> None:
    state = small_world()
    world = state.world
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
        check_extension(reused, state.world)


def test_more_map_is_offered_only_once_every_place_is_known() -> None:
    state = small_world()
    assert ENGINE.player_view(state).action is None

    draft = state.draft()
    for place in draft.world.places.values():
        place.known = True
    assert ENGINE.player_view(draft.commit()).action == MORE_MAP
