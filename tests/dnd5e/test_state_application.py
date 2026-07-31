import pytest
from fivee_test_support import state as state

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.entities import ActorEntity, ItemEntity, LocationEntity
from aidm.domain.state import GameState
from aidm_5e.state import actor_of, created_state, dnd5e_state

MARA = EntityId("mara")


def item(state: GameState, entity_id: str) -> ItemEntity:
    return state.world.require_kind(EntityId(entity_id), ItemEntity)


def where(state: GameState, entity_id: str) -> LocationEntity:
    return state.world.require_kind(EntityId(entity_id), LocationEntity)


def test_take_drop_and_hp(state: GameState) -> None:
    _ = state.move_item(item(state, "vault_map"), state.player)
    _ = state.move_item(item(state, "lantern"), where(state, "study"))
    _ = actor_of(state, PLAYER_ID).stats.apply_hp_delta(-3)
    result = state.committed()

    # vault_map picked up, lantern dropped in the study
    carried = [e.id for e in result.world.carried_by(PLAYER_ID)]
    assert carried == [EntityId("vault_map")]
    assert item(result, "vault_map").container_id == PLAYER_ID
    assert item(result, "lantern").container_id == "study"  # now lies here
    assert actor_of(result, PLAYER_ID).stats.hp == 7


def test_give_moves_an_item_into_another_actors_inventory(state: GameState) -> None:
    mara = state.world.require_kind(MARA, ActorEntity)
    _ = state.move_item(item(state, "lantern"), mara)
    result = state.committed()

    assert result.world.carried_by(PLAYER_ID) == ()
    assert [e.id for e in result.world.carried_by(MARA)] == [EntityId("lantern")]


def test_hp_is_clamped_for_every_actor(state: GameState) -> None:
    player = actor_of(state, PLAYER_ID)
    assert player.stats.apply_hp_delta(-99) == -10
    assert player.stats.hp == 0
    assert player.stats.apply_hp_delta(99) == 10
    assert player.stats.hp == 10
    mara = actor_of(state, MARA)
    _ = mara.stats.apply_hp_delta(-99)
    assert mara.stats.hp == 0
    assert actor_of(state.committed(), MARA).stats.hp == 0


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


def test_revealing_a_known_entity_states_nothing(state: GameState) -> None:
    assert state.reveal(state.world.require(EntityId("mara"))) == []


def test_create_appends_and_gains_engine_state(state: GameState) -> None:
    elgin = ActorEntity(
        id=EntityId("elgin"),
        name="Elgin",
        brief="An apothecary.",
        authored=False,
        location_id=EntityId("study"),
    )
    _ = state.add(elgin)
    created_state(state, elgin)
    result = state.committed()

    assert list(result.world.entities.values())[-1] == elgin
    assert dnd5e_state(result).actor(elgin.id).progression is None


def test_impossible_topology_fails_fast(state: GameState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        state.reveal(state.world.require(EntityId("nobody")))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = item(state, "nobody")
    with pytest.raises(ValueError, match="it is a location"):
        _ = state.world.require_kind(EntityId("study"), ActorEntity)
    with pytest.raises(ValueError, match="already exists"):
        _ = state.add(state.player)
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
    setattr(state.world.entities[entity_id], field, container)
    with pytest.raises(ValueError):
        state.committed()


def test_engine_state_must_track_every_world_actor(state: GameState) -> None:
    del dnd5e_state(state).actors[MARA]
    with pytest.raises(ValueError, match="does not track the world"):
        state.committed()


def test_a_refused_commit_leaves_the_draft_and_its_source_alone(state: GameState) -> None:
    """The draft is discarded, so a half-mutated one is safe; the caller rebinds only on success."""
    committed = state.committed()
    before = committed.model_dump_json()
    draft = committed.draft()
    _ = draft.move_actor(draft.player, where(draft, "vault"))
    del dnd5e_state(draft).actors[MARA]

    with pytest.raises(ValueError, match="does not track the world"):
        draft.committed()

    assert committed.model_dump_json() == before
    assert draft.player.location_id == "vault"  # the failed draft keeps its half-applied change
