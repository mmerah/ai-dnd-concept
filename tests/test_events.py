import pytest

from aidm.domain.models import (
    PLAYER_ID,
    ActorEntity,
    EntityCreated,
    EntityDiscovered,
    EntityId,
    GameState,
    HpChanged,
    ItemEntity,
    ItemMoved,
    Moved,
    Wounds,
    updated,
)
from aidm.domain.reducer import apply, render

MARA = EntityId("mara")


def hurt(target_id: EntityId, name: str, delta: int, after: Wounds = "hurt") -> HpChanged:
    return HpChanged(target_id=target_id, target_name=name, delta=delta, wounds=after)


def test_take_drop_and_hp(state: GameState) -> None:
    result = apply(
        state,
        [
            ItemMoved(
                item_id=EntityId("vault_map"),
                item_name="the vault map",
                to_id=PLAYER_ID,
                to_name="Kael",
                to_kind="actor",
            ),
            ItemMoved(
                item_id=EntityId("lantern"),
                item_name="a lantern",
                to_id=EntityId("study"),
                to_name="the study",
                to_kind="location",
            ),
            hurt(PLAYER_ID, "Kael", -3),
        ],
    )
    # vault_map picked up, lantern dropped in the study
    carried = [e.id for e in result.world.carried_by(PLAYER_ID)]
    assert carried == [EntityId("vault_map")]
    vault_map = result.world.entities[EntityId("vault_map")]
    lantern = result.world.entities[EntityId("lantern")]
    assert isinstance(vault_map, ItemEntity) and vault_map.container_id == PLAYER_ID
    assert isinstance(lantern, ItemEntity) and lantern.container_id == "study"  # now lies here
    assert result.player.stats.hp == 7


def test_give_moves_an_item_into_another_actors_inventory(state: GameState) -> None:
    result = apply(
        state,
        [
            ItemMoved(
                item_id=EntityId("lantern"),
                item_name="a lantern",
                to_id=MARA,
                to_name="Mara",
                to_kind="actor",
            )
        ],
    )
    assert result.world.carried_by(PLAYER_ID) == []
    assert [e.id for e in result.world.carried_by(MARA)] == [EntityId("lantern")]


def test_hp_is_clamped_for_every_actor(state: GameState) -> None:
    assert apply(state, [hurt(PLAYER_ID, "Kael", -99, "down")]).player.stats.hp == 0
    assert apply(state, [hurt(PLAYER_ID, "Kael", 99, "unharmed")]).player.stats.hp == 10
    mara = apply(state, [hurt(MARA, "Mara", -99, "down")]).world.entities[MARA]
    assert isinstance(mara, ActorEntity) and mara.stats.hp == 0


def test_the_narrator_never_reads_another_actors_hit_points(state: GameState) -> None:
    """`render` is the whole of the Narrator's mechanical window."""
    assert render([hurt(PLAYER_ID, "Kael", -3)]) == "- hp -3"
    assert render([hurt(MARA, "Mara", -3, "badly hurt")]) == "- Mara is badly hurt"


def test_move_the_player(state: GameState) -> None:
    moved = Moved(
        actor_id=PLAYER_ID,
        actor_name="Kael",
        location_id=EntityId("vault"),
        location_name="the vault",
    )
    assert apply(state, [moved]).player.location_id == "vault"


def test_move_another_actor(state: GameState) -> None:
    moved = Moved(
        actor_id=MARA,
        actor_name="Mara",
        location_id=EntityId("vault"),
        location_name="the vault",
    )
    mara = apply(state, [moved]).world.entities[MARA]
    assert isinstance(mara, ActorEntity) and mara.location_id == "vault"


def test_discover_reveals_only_the_target(state: GameState) -> None:
    result = apply(state, [EntityDiscovered(entity_id=EntityId("elena"), name="Elena")])
    known = {e.id: e.known for e in result.world.entities.values()}
    assert known == {
        "study": True,
        "vault": False,
        "player": True,  # the player is canon they already know
        "mara": True,
        "elena": True,
        "vault_map": False,
        "lantern": True,
    }


def test_create_appends(state: GameState) -> None:
    elgin = ActorEntity(
        id=EntityId("elgin"),
        name="Elgin",
        brief="An apothecary.",
        authored=False,
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
            [
                ItemMoved(
                    item_id=EntityId("nobody"),
                    item_name="a ghost",
                    to_id=PLAYER_ID,
                    to_name="Kael",
                    to_kind="actor",
                )
            ],
        )
    with pytest.raises(ValueError):
        apply(
            state,
            [
                Moved(
                    actor_id=PLAYER_ID,
                    actor_name="Kael",
                    location_id=EntityId("nowhere"),
                    location_name="Nowhere",
                )
            ],
        )
    with pytest.raises(ValueError):  # a location has no hit points
        apply(state, [hurt(EntityId("study"), "the study", -1)])


@pytest.mark.parametrize(
    ("entity_id", "field", "container"),
    [
        (EntityId("lantern"), "container_id", EntityId("vault_map")),  # an item holds nothing
        (EntityId("lantern"), "container_id", EntityId("lantern")),  # nor does it hold itself
        (EntityId("lantern"), "container_id", EntityId("nowhere")),  # nor does a ghost
        (PLAYER_ID, "location_id", EntityId("mara")),  # an actor stands in a location, not a person
    ],
)
def test_a_world_that_puts_something_nowhere_real_is_refused(
    state: GameState, entity_id: EntityId, field: str, container: EntityId
) -> None:
    """One required container id per item is the whole point of the shape: what used to need a
    held-xor-located reconciliation is now a single lookup that either resolves or raises."""
    broken = updated(state.world.entities[entity_id], **{field: container})
    with pytest.raises(ValueError):
        updated(
            state, world=updated(state.world, entities={**state.world.entities, entity_id: broken})
        )
