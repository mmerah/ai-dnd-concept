import pytest
from fivee_test_support import actor_of
from fivee_test_support import state as state

from aidm.base import PLAYER_ID, ActorEntity, EntityId, ItemEntity, LocationEntity
from aidm.engines.dnd5e.access import Dnd5eWorld
from aidm.engines.dnd5e.state import Dnd5eActorState, StatBlock
from aidm.world import GameState

MARA = EntityId("mara")


def item(state: GameState, entity_id: str) -> ItemEntity:
    return state.world.require_kind(EntityId(entity_id), ItemEntity)


def where(state: GameState, entity_id: str) -> LocationEntity:
    return state.world.require_kind(EntityId(entity_id), LocationEntity)


def test_take_drop_and_hp(state: GameState) -> None:
    _ = state.move_item(item(state, "vault_map"), state.player)
    _ = state.move_item(item(state, "lantern"), where(state, "study"))
    world = Dnd5eWorld(state=state)
    _ = world.player().stats.apply_hp_delta(-3)
    result = world.commit()

    # vault_map picked up, lantern dropped in the study
    carried = [record.entity.id for record in result.world.carried_by(PLAYER_ID)]
    assert carried == [EntityId("vault_map")]
    assert item(result, "vault_map").container_id == PLAYER_ID
    assert item(result, "lantern").container_id == "study"  # now lies here
    assert actor_of(result, PLAYER_ID).stats.hp == 7


def test_give_moves_an_item_into_another_actors_inventory(state: GameState) -> None:
    mara = state.world.require_kind(MARA, ActorEntity)
    _ = state.move_item(item(state, "lantern"), mara)
    result = state.committed()

    assert result.world.carried_by(PLAYER_ID) == ()
    assert [record.entity.id for record in result.world.carried_by(MARA)] == [EntityId("lantern")]


def test_hp_is_clamped_for_every_actor(state: GameState) -> None:
    world = Dnd5eWorld(state=state)
    player = world.player()
    assert player.stats.apply_hp_delta(-99) == -10
    assert player.stats.hp == 0
    assert player.stats.apply_hp_delta(99) == 10
    assert player.stats.hp == 10
    mara = world.actor(MARA)
    _ = mara.stats.apply_hp_delta(-99)
    assert mara.stats.hp == 0
    assert actor_of(world.commit(), MARA).stats.hp == 0


def test_move_the_player(state: GameState) -> None:
    _ = state.move_actor(state.player, where(state, "vault"))
    assert state.committed().player.location_id == "vault"


def test_move_another_actor(state: GameState) -> None:
    mara = state.world.require_kind(MARA, ActorEntity)
    _ = state.move_actor(mara, where(state, "vault"))
    assert actor_of(state.committed(), MARA).location_id == "vault"


def test_discover_reveals_only_the_target(state: GameState) -> None:
    _ = state.reveal(state.world.require(EntityId("elena")))
    result = state.committed()

    known = {entity.id: entity.known for entity in result.world.entities()}
    assert known == {
        "study": True,
        "vault": False,
        "player": True,  # the player is canon they already know
        "mara": True,
        "elena": True,
        "vault_map": False,
        "lantern": True,
    }


def test_revealing_a_known_entity_states_nothing(state: GameState) -> None:
    assert state.reveal(state.world.require(EntityId("mara"))) == []


def test_create_appends_a_record_carrying_engine_state(state: GameState) -> None:
    elgin = ActorEntity(
        id=EntityId("elgin"),
        name="Elgin",
        brief="An apothecary.",
        location_id=EntityId("study"),
    )
    _ = state.add(elgin, Dnd5eActorState(stats=StatBlock()).model_dump(mode="json"))
    result = state.committed()

    assert list(result.world.actors)[-1] == elgin.id
    assert actor_of(result, elgin.id).entity == elgin
    assert actor_of(result, elgin.id).progression is None


def test_impossible_topology_fails_fast(state: GameState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        state.reveal(state.world.require(EntityId("nobody")))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = item(state, "nobody")
    with pytest.raises(ValueError, match="it is a location"):
        _ = state.world.require_kind(EntityId("study"), ActorEntity)
    with pytest.raises(ValueError, match="already exists"):
        _ = state.add(state.player, Dnd5eActorState(stats=StatBlock()).model_dump(mode="json"))
    with pytest.raises(ValueError, match="it is a location"):  # a location has no hit points
        _ = actor_of(state, EntityId("study"))


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
    setattr(state.world.require(entity_id), field, container)
    with pytest.raises(ValueError):
        state.committed()


def test_a_refused_commit_leaves_the_draft_and_its_source_alone(state: GameState) -> None:
    """The draft is discarded, so a half-mutated one is safe; the caller rebinds only on success."""
    committed = state.committed()
    before = committed.model_dump_json()
    draft = committed.draft()
    _ = draft.move_actor(draft.player, where(draft, "vault"))
    item(draft, "lantern").container_id = EntityId("nowhere")

    with pytest.raises(ValueError, match="which holds nothing"):
        draft.committed()

    assert committed.model_dump_json() == before
    assert draft.player.location_id == "vault"  # the failed draft keeps its half-applied change
