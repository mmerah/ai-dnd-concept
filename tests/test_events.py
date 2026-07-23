import pytest

from aidm.domain.events import (
    EntityCreated,
    EntityDiscovered,
    HpChanged,
    InventoryChanged,
    Moved,
    apply,
)
from aidm.domain.models import Entity, EntityId, GameState


def test_inventory_and_hp(state: GameState) -> None:
    result = apply(
        state,
        [
            InventoryChanged(item="a map", delta=1),
            InventoryChanged(item="a lantern", delta=-1),
            HpChanged(delta=-3),
        ],
    )
    assert result.character.inventory == ["a map"]
    assert result.character.hp == 7
    assert result.character.inventory is not state.character.inventory


def test_hp_is_clamped(state: GameState) -> None:
    assert apply(state, [HpChanged(delta=-99)]).character.hp == 0
    assert apply(state, [HpChanged(delta=99)]).character.hp == state.character.max_hp


def test_move(state: GameState) -> None:
    assert apply(state, [Moved(location="the vault")]).character.location == "the vault"


def test_discover_reveals_only_the_target(state: GameState) -> None:
    result = apply(state, [EntityDiscovered(entity_id=EntityId("elena"), name="Elena")])
    known = {e.id: e.known for e in result.world.entities}
    assert known == {"mara": True, "elena": True, "vault_map": False}


def test_create_appends(state: GameState) -> None:
    elgin = Entity(
        id=EntityId("elgin"), kind="npc", name="Elgin", brief="An apothecary.", authored=False
    )
    assert apply(state, [EntityCreated(entity=elgin)]).world.entities[-1] == elgin


def test_impossible_events_fail_fast(state: GameState) -> None:
    with pytest.raises(ValueError):
        apply(state, [EntityDiscovered(entity_id=EntityId("nobody"), name="Nobody")])
    with pytest.raises(ValueError):
        apply(state, [InventoryChanged(item="a sword", delta=-1)])
