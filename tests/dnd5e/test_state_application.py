from random import Random

import pytest
from fivee_test_support import actor_of, ruleset
from fivee_test_support import state as state

from aidm.core.base import PLAYER_ID, Entity, EntityId
from aidm.engines.dnd5e.access import Dnd5eWorld
from aidm.engines.dnd5e.state import Dnd5eActorState, Dnd5eState, StatBlock

MARA = EntityId("mara")


def world_of(state: Dnd5eState) -> Dnd5eWorld:
    return Dnd5eWorld(state=state, rng=Random(0), ruleset=ruleset())


def item(state: Dnd5eState, entity_id: str) -> Entity:
    return state.world.require_kind(EntityId(entity_id), "item")


def where(state: Dnd5eState, entity_id: str) -> Entity:
    return state.world.require_kind(EntityId(entity_id), "location")


def test_take_drop_and_hp(state: Dnd5eState) -> None:
    _ = state.move(item(state, "vault_map"), state.player)
    _ = state.move(item(state, "lantern"), where(state, "study"))
    world = world_of(state)
    _ = world.player().stats.apply_hp_delta(-3)
    result = world.commit()

    # vault_map picked up, lantern dropped in the study
    carried = [entity.id for entity in result.world.children(PLAYER_ID, "item")]
    assert carried == [EntityId("vault_map")]
    assert item(result, "vault_map").parent_id == PLAYER_ID
    assert item(result, "lantern").parent_id == "study"  # now lies here
    assert actor_of(result, PLAYER_ID).stats.hp == 7


def test_give_moves_an_item_into_another_actors_inventory(state: Dnd5eState) -> None:
    mara = state.world.require_kind(MARA, "actor")
    _ = state.move(item(state, "lantern"), mara)
    result = state.committed()

    assert result.world.children(PLAYER_ID, "item") == ()
    assert [entity.id for entity in result.world.children(MARA, "item")] == [EntityId("lantern")]


def test_hp_is_clamped_for_every_actor(state: Dnd5eState) -> None:
    world = world_of(state)
    player = world.player()
    assert player.stats.apply_hp_delta(-99) == -10
    assert player.stats.hp == 0
    assert player.stats.apply_hp_delta(99) == 10
    assert player.stats.hp == 10
    mara = world.actor(MARA)
    _ = mara.stats.apply_hp_delta(-99)
    assert mara.stats.hp == 0
    assert actor_of(world.commit(), MARA).stats.hp == 0


def test_move_the_player(state: Dnd5eState) -> None:
    _ = state.move(state.player, where(state, "vault"))
    assert state.committed().player_location == "vault"


def test_move_another_actor(state: Dnd5eState) -> None:
    mara = state.world.require_kind(MARA, "actor")
    _ = state.move(mara, where(state, "vault"))
    assert actor_of(state.committed(), MARA).entity.parent_id == "vault"


def test_discover_reveals_only_the_target(state: Dnd5eState) -> None:
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


def test_revealing_a_known_entity_states_nothing(state: Dnd5eState) -> None:
    assert state.reveal(state.world.require(EntityId("mara"))) == []


def test_create_appends_a_record_carrying_engine_state(state: Dnd5eState) -> None:
    elgin = Entity(
        id=EntityId("elgin"),
        kind="actor",
        name="Elgin",
        brief="An apothecary.",
        parent_id=EntityId("study"),
    )
    _ = state.add(elgin, Dnd5eActorState(stats=StatBlock()))
    result = state.committed()

    assert list(result.world.entities("actor"))[-1].id == elgin.id
    assert actor_of(result, elgin.id).entity == elgin
    assert actor_of(result, elgin.id).progression is None


def test_impossible_topology_fails_fast(state: Dnd5eState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        state.reveal(state.world.require(EntityId("nobody")))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = item(state, "nobody")
    with pytest.raises(ValueError, match="it is a location"):
        _ = state.world.require_kind(EntityId("study"), "actor")
    with pytest.raises(ValueError, match="already exists"):
        _ = state.add(state.player, Dnd5eActorState(stats=StatBlock()))
    with pytest.raises(ValueError, match="it is a location"):  # a location has no hit points
        _ = actor_of(state, EntityId("study"))


@pytest.mark.parametrize(
    ("entity_id", "container"),
    [
        (EntityId("lantern"), EntityId("vault_map")),  # an item holds nothing
        (EntityId("lantern"), EntityId("lantern")),  # nor does it hold itself
        (EntityId("lantern"), EntityId("nowhere")),  # nor does a ghost
        (PLAYER_ID, EntityId("mara")),  # an actor stands in a location, not a person
    ],
)
def test_a_world_that_puts_something_nowhere_real_is_refused(
    state: Dnd5eState, entity_id: EntityId, container: EntityId
) -> None:
    """One required parent id per entity is the whole point of the shape: what used to need a
    held-xor-located reconciliation is now a single lookup that either resolves or raises."""
    state.world.require(entity_id).parent_id = container
    with pytest.raises(ValueError):
        state.committed()


def test_a_refused_commit_leaves_the_draft_and_its_source_alone(state: Dnd5eState) -> None:
    """The draft is discarded, so a half-mutated one is safe; the caller rebinds only on success."""
    committed = state.committed()
    before = committed.model_dump_json()
    draft = committed.draft()
    _ = draft.move(draft.player, where(draft, "vault"))
    item(draft, "lantern").parent_id = EntityId("nowhere")

    with pytest.raises(ValueError, match="not in a valid"):
        draft.committed()

    assert committed.model_dump_json() == before
    assert draft.player_location == "vault"  # the failed draft keeps its half-applied change
