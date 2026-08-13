import pytest
from core_test_support import initialized

from aidm.state.apply import apply_effect
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.effects import (
    GainImprovisedItem,
    Move,
    RelationChange,
    Reveal,
    TraitChange,
    WorldOp,
)
from aidm.state.facts import Fact
from aidm.state.world import CONNECTED, LOCKED_TAG, PARTY_MEMBER

BELL_TOWER = EntityId("bell_tower")
CLOISTER = EntityId("cloister")
STUDY = EntityId("study")
ELENA = EntityId("elena")
LANTERN = EntityId("lantern")
MARA = EntityId("mara")
RAT = EntityId("cloister_rat")
TOMAS = EntityId("tomas")
VAULT = EntityId("vault")
VAULT_MAP = EntityId("vault_map")


class Applied:
    """One turn's draft and the effects landing on it, as a resolver would apply them."""

    def __init__(self) -> None:
        _, state = initialized()
        self.draft = state.draft()

    def __call__(self, effect: WorldOp) -> list[Fact]:
        return apply_effect(self.draft, effect)

    def kinds(self, effect: WorldOp) -> list[str]:
        return [fact.kind for fact in self(effect)]


def test_world_effects_move_and_reveal_only_what_the_player_witnesses() -> None:
    turn = Applied()

    assert turn(Reveal(entity_id=MARA)) == []
    assert turn.kinds(Reveal(entity_id=VAULT_MAP)) == ["entity_discovered"]
    arrived = Move(to_id=STUDY, entity_id=ELENA)
    assert turn.kinds(arrived) == ["entity_discovered", "entity_moved"]
    assert turn.kinds(Move(to_id=VAULT, entity_id=MARA)) == ["entity_moved"]
    assert turn.kinds(Move(to_id=CLOISTER)) == ["entity_moved"]
    hidden = RelationChange(mode="remove", kind=CONNECTED, source=CLOISTER, target=VAULT)
    assert turn(hidden)[0].narrator is None, "a hidden tie's trace names an unmet place"

    with pytest.raises(ValueError, match="would not be witnessed"):
        _ = turn(Move(to_id=VAULT, entity_id=ELENA))
    with pytest.raises(ValueError, match="is a actor, not a location"):
        _ = turn(Move(to_id=MARA))
    with pytest.raises(ValueError, match="name it in `to_id`"):
        _ = turn(Move(entity_id=ELENA))
    with pytest.raises(ValueError, match="unknown entity id"):
        _ = turn(Reveal(entity_id=EntityId("ghost")))


def test_movement_follows_the_connections_the_world_authors() -> None:
    turn = Applied()

    assert turn.kinds(Move(to_id=CLOISTER)) == ["entity_moved"]
    with pytest.raises(ValueError, match="has not found the way to the bell tower"):
        _ = turn(Move(to_id=BELL_TOWER))
    revealed = RelationChange(mode="reveal", kind=CONNECTED, source=CLOISTER, target=BELL_TOWER)
    assert turn.kinds(revealed) == ["entity_discovered", "relation_revealed"]
    assert turn.kinds(Move(to_id=BELL_TOWER)) == ["entity_moved"]

    _ = turn(Move(to_id=CLOISTER))
    # `cloister`—`vault` is authored in world.json already carrying the `locked` tag.
    _ = turn(RelationChange(mode="reveal", kind=CONNECTED, source=CLOISTER, target=VAULT))
    with pytest.raises(ValueError, match="is locked"):
        _ = turn(Move(to_id=VAULT))
    with pytest.raises(ValueError, match="belongs to no other mode"):
        _ = RelationChange(mode="untag", kind=CONNECTED, source=CLOISTER, target=VAULT)
    _ = turn(
        RelationChange(mode="untag", kind=CONNECTED, source=CLOISTER, target=VAULT, tag=LOCKED_TAG)
    )
    assert turn.kinds(Move(to_id=VAULT)) == ["entity_moved"]


def test_a_party_member_travels_with_the_player() -> None:
    turn = Applied()

    joined = RelationChange(
        mode="add", kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID, why="Mara comes along"
    )
    assert turn.kinds(joined) == ["relation_added"]
    moved = turn(Move(to_id=CLOISTER))
    assert [fact.data["entity_id"] for fact in moved] == [PLAYER_ID, MARA]

    left = RelationChange(mode="remove", kind=PARTY_MEMBER, source=MARA, target=PLAYER_ID)
    assert turn.kinds(left) == ["relation_removed"]
    assert turn.kinds(Move(to_id=STUDY)) == ["entity_moved"]


def test_inventory_effects_gate_on_position_and_carrying() -> None:
    turn = Applied()

    took = turn(Move(entity_id=VAULT_MAP))[1]
    assert (took.data["entity_id"], took.data["to_id"]) == (VAULT_MAP, PLAYER_ID)
    with pytest.raises(ValueError, match="already carries"):
        _ = turn(Move(entity_id=VAULT_MAP))
    with pytest.raises(ValueError, match="player's own location"):
        _ = turn(Move(entity_id=LANTERN, to_id=VAULT))
    (dropped,) = turn(Move(entity_id=LANTERN, to_id=STUDY))
    assert (dropped.data["entity_id"], dropped.data["to_kind"]) == (LANTERN, "location")
    (given,) = turn(Move(entity_id=VAULT_MAP, to_id=MARA))
    assert (given.data["entity_id"], given.data["to_id"]) == (VAULT_MAP, MARA)

    created, carried = turn(GainImprovisedItem(item_name="a rusty key"))
    assert created.data["name"] == "a rusty key"
    assert carried.data["entity_id"] == created.data["entity_id"]

    with pytest.raises(ValueError, match="not loose at the player's location"):
        _ = turn(Move(entity_id=VAULT_MAP))
    with pytest.raises(ValueError, match="does not carry"):
        _ = turn(Move(entity_id=VAULT_MAP, to_id=STUDY))
    with pytest.raises(ValueError, match="not here with the player"):
        _ = turn(Move(entity_id=LANTERN, to_id=TOMAS))


def test_trait_changes_round_trip_and_refuse_what_the_entity_does_not_carry() -> None:
    turn = Applied()

    (added,) = turn(TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="hunted", text="watched"))
    assert added.data["trait_id"] == "hunted"
    assert turn.draft.player.trait("hunted") is not None

    removed = TraitChange(mode="remove", entity_id=PLAYER_ID, trait_id="hunted")
    assert turn.kinds(removed) == ["trait_removed"]

    with pytest.raises(ValueError, match="carries no trait"):
        _ = turn(TraitChange(mode="remove", entity_id=PLAYER_ID, trait_id="hunted"))
    # Kael's character sheet already carries `relic-hunter` as an authored skill.
    with pytest.raises(ValueError, match="already carries the trait"):
        _ = turn(TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="relic-hunter"))


def test_acting_on_an_unrevealed_actor_reveals_it_before_its_traits_change() -> None:
    """The leak rule: an actor is revealed by being acted on, an item or a place is not."""
    turn = Applied()
    _ = turn(Move(to_id=CLOISTER))

    change = TraitChange(mode="add", entity_id=RAT, trait_id="hurt", why="the lantern")
    kinds = turn.kinds(change)

    assert kinds == ["entity_discovered", "trait_added"]
