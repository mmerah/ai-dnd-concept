import pytest

from aidm.domain.models import (
    PLAYER_ID,
    EntityCreated,
    EntityDiscovered,
    EntityId,
    GameState,
    HpChanged,
    ItemEntity,
    ItemMoved,
    Moved,
    NpcEntity,
)
from aidm.domain.reducer import apply


def test_take_drop_and_hp(state: GameState) -> None:
    result = apply(
        state,
        [
            ItemMoved(
                item_id=EntityId("vault_map"),
                item_name="the vault map",
                to_id=PLAYER_ID,
                to_name="Kael",
                to_kind="player",
            ),
            ItemMoved(
                item_id=EntityId("lantern"),
                item_name="a lantern",
                to_id=EntityId("study"),
                to_name="the study",
                to_kind="location",
            ),
            HpChanged(delta=-3),
        ],
    )
    # vault_map picked up, lantern dropped in the study
    assert result.character.inventory == [EntityId("vault_map")]
    vault_map = result.world.entities[EntityId("vault_map")]
    lantern = result.world.entities[EntityId("lantern")]
    assert isinstance(vault_map, ItemEntity) and vault_map.location_id is None  # held: no location
    assert isinstance(lantern, ItemEntity) and lantern.location_id == "study"  # now lies here
    assert result.character.hp == 7
    assert result.character.inventory is not state.character.inventory


def test_give_moves_an_item_into_an_npc_inventory(state: GameState) -> None:
    result = apply(
        state,
        [
            ItemMoved(
                item_id=EntityId("lantern"),
                item_name="a lantern",
                to_id=EntityId("mara"),
                to_name="Mara",
                to_kind="npc",
            )
        ],
    )
    assert result.character.inventory == []
    mara = result.world.entities[EntityId("mara")]
    assert isinstance(mara, NpcEntity) and mara.inventory == [EntityId("lantern")]


def test_hp_is_clamped(state: GameState) -> None:
    assert apply(state, [HpChanged(delta=-99)]).character.hp == 0
    assert apply(state, [HpChanged(delta=99)]).character.hp == state.character.max_hp


def test_move_the_player(state: GameState) -> None:
    moved = Moved(
        subject_id=PLAYER_ID, subject_name="Kael", location_id=EntityId("vault"),
        location_name="the vault",
    )
    assert apply(state, [moved]).character.location_id == "vault"


def test_move_an_npc(state: GameState) -> None:
    moved = Moved(
        subject_id=EntityId("mara"), subject_name="Mara", location_id=EntityId("vault"),
        location_name="the vault",
    )
    mara = apply(state, [moved]).world.entities[EntityId("mara")]
    assert isinstance(mara, NpcEntity) and mara.location_id == "vault"


def test_discover_reveals_only_the_target(state: GameState) -> None:
    result = apply(state, [EntityDiscovered(entity_id=EntityId("elena"), name="Elena")])
    known = {e.id: e.known for e in result.world.entities.values()}
    assert known == {
        "study": True,
        "vault": False,
        "mara": True,
        "elena": True,
        "vault_map": False,
        "lantern": True,
    }


def test_create_appends(state: GameState) -> None:
    elgin = NpcEntity(
        id=EntityId("elgin"), name="Elgin", brief="An apothecary.", authored=False,
        location_id=EntityId("study"),
    )
    entities = apply(state, [EntityCreated(entity=elgin)]).world.entities
    assert list(entities.values())[-1] == elgin


def test_impossible_events_fail_fast(state: GameState) -> None:
    with pytest.raises(ValueError):
        apply(state, [EntityDiscovered(entity_id=EntityId("nobody"), name="Nobody")])
    with pytest.raises(ValueError):
        apply(
            state,
            [ItemMoved(
                item_id=EntityId("nobody"), item_name="a ghost", to_id=PLAYER_ID,
                to_name="Kael", to_kind="player",
            )],
        )
    with pytest.raises(ValueError):
        apply(
            state,
            [Moved(
                subject_id=PLAYER_ID, subject_name="Kael", location_id=EntityId("nowhere"),
                location_name="Nowhere",
            )],
        )
