import pytest
from core_test_support import TUNNELGOONS, game
from tunnelgoons_test_support import small_world

from aidm.core.entities import EntityId
from aidm.engines.tunnelgoons.world import Item, Place, TunnelGoonsGame, Way
from aidm.engines.tunnelgoons.worldsmith import (
    MapDraft,
    apply_extension,
    install_extension,
    map_exhausted,
    map_refusal,
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


def test_apply_extension_joins_at_the_current_place_and_the_world_validates() -> None:
    state = small_world()
    world = state.payload.world
    anchor = world.player.place

    apply_extension(world, _region())

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

    with pytest.raises(ValueError, match="not already in the world"):
        apply_extension(state.payload.world, reused)


def test_map_exhausted_is_false_on_the_shipped_map_and_true_once_every_place_is_known() -> None:
    state = small_world()
    assert not map_exhausted(state)

    draft = state.draft()
    for place in draft.payload.world.places.values():
        place.known = True
    assert map_exhausted(draft.committed())


def test_install_extension_on_a_game_from_the_engine() -> None:
    draft = _tunnelgoons_game().draft()
    anchor = draft.payload.world.player.place

    facts = install_extension(draft, _region())

    assert [fact.kind for fact in facts] == ["region_added"]
    assert not facts[0].told
    assert FAR_HALL in draft.payload.world.places
    assert draft.payload.world.way(anchor, FAR_HALL) is not None
