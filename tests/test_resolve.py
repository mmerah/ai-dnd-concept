"""The resolver is the single sink from the Director's mechanics to events — pure, seeded.
The mechanics are a recursive consequence list: `roll_check` nests branches, `roll_dice` binds a
value a later `damage`/`heal` reads via `Ref`. Positions gate take/drop/give."""

from random import Random

import pytest

from aidm.domain.models import (
    PLAYER_ID,
    CheckRolled,
    Consequence,
    Damage,
    Discover,
    DropItem,
    EntityCreated,
    EntityDiscovered,
    EntityId,
    GainImprovisedItem,
    GameState,
    GiveItem,
    Heal,
    HpChanged,
    ItemMoved,
    Move,
    Moved,
    Ref,
    RollCheck,
    RollDice,
    TakeItem,
    updated,
)
from aidm.engine.resolve import resolve

# Kael's wisdom is 14 (+2). Random(0)'s first d20 is 13 (-> 15, passes DC 12); Random(2)'s is 2.
PASS, FAIL = Random(0), Random(2)


def relocated(state: GameState, entity_id: EntityId, location_id: EntityId) -> GameState:
    entity = updated(state.world.entities[entity_id], location_id=location_id)
    entities = {**state.world.entities, entity_id: entity}
    return updated(state, world=updated(state.world, entities=entities))


def test_top_level_consequences_all_apply_in_order(state: GameState) -> None:
    mechanics: list[Consequence] = [Damage(amount=2), Move(location_id=EntityId("vault"))]
    events = resolve(mechanics, state, PASS)
    assert [e.type for e in events] == ["hp_changed", "entity_discovered", "moved"]
    hp, moved = events[0], events[2]
    assert isinstance(hp, HpChanged) and hp.delta == -2
    assert isinstance(moved, Moved) and (moved.actor_id, moved.location_id) == ("player", "vault")


def test_check_success_selects_on_success(state: GameState) -> None:
    mechanics: list[Consequence] = [
        RollCheck(
            ability="wisdom",
            dc=12,
            on_success=[GainImprovisedItem(item_name="a torch")],
            on_failure=[Damage(amount=5)],
        )
    ]
    events = resolve(mechanics, state, PASS)
    # improvised gain promotes the item to canon first, then adds it to inventory
    assert [e.type for e in events] == ["check_rolled", "entity_created", "item_moved"]
    rolled, created = events[0], events[1]
    assert isinstance(rolled, CheckRolled) and rolled.success
    assert isinstance(created, EntityCreated) and created.entity.name == "a torch"


def test_check_failure_selects_on_failure(state: GameState) -> None:
    mechanics: list[Consequence] = [
        RollCheck(
            ability="wisdom",
            dc=12,
            on_success=[GainImprovisedItem(item_name="a torch")],
            on_failure=[Damage(amount=5)],
        )
    ]
    events = resolve(mechanics, state, FAIL)
    assert [e.type for e in events] == ["check_rolled", "hp_changed"]
    rolled, hp = events[0], events[1]
    assert isinstance(rolled, CheckRolled) and not rolled.success
    assert isinstance(hp, HpChanged) and hp.delta == -5


def test_heal_adds_hp(state: GameState) -> None:
    (hp,) = resolve([Heal(amount=3)], state, PASS)
    assert isinstance(hp, HpChanged) and hp.delta == 3


def test_take_a_present_item_reveals_it_and_moves_it_to_the_player(state: GameState) -> None:
    events = resolve([TakeItem(item_id=EntityId("vault_map"))], state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "item_moved"]
    took = events[1]
    assert isinstance(took, ItemMoved)
    assert (took.item_id, took.item_name, took.to_id) == ("vault_map", "the vault map", PLAYER_ID)


def test_take_something_not_here_fails(state: GameState) -> None:
    """The lantern is carried (no location), so it is not lying here to be taken."""
    with pytest.raises(ValueError, match="not at the player's location"):
        resolve([TakeItem(item_id=EntityId("lantern"))], state, PASS)


def test_drop_puts_a_held_item_at_the_players_location(state: GameState) -> None:
    (dropped,) = resolve([DropItem(item_id=EntityId("lantern"))], state, PASS)
    assert isinstance(dropped, ItemMoved)
    assert (dropped.item_id, dropped.to_id, dropped.to_kind) == ("lantern", "study", "location")


def test_drop_something_not_held_fails(state: GameState) -> None:
    with pytest.raises(ValueError, match="not carrying"):
        resolve([DropItem(item_id=EntityId("vault_map"))], state, PASS)


def test_give_hands_a_held_item_to_a_present_actor(state: GameState) -> None:
    give = GiveItem(item_id=EntityId("lantern"), actor_id=EntityId("mara"))
    (given,) = resolve([give], state, PASS)
    assert isinstance(given, ItemMoved)
    assert (given.item_id, given.to_id, given.to_kind) == ("lantern", "mara", "actor")


def test_giving_an_item_to_the_player_is_refused(state: GameState) -> None:
    with pytest.raises(ValueError, match="already hold it"):
        resolve([GiveItem(item_id=EntityId("lantern"), actor_id=PLAYER_ID)], state, PASS)


def test_give_to_an_absent_actor_fails(state: GameState) -> None:
    """Move Mara away first, then giving to her must fail: she is no longer here."""
    away = relocated(state, EntityId("mara"), EntityId("vault"))
    with pytest.raises(ValueError, match="not at the player's location"):
        resolve([GiveItem(item_id=EntityId("lantern"), actor_id=EntityId("mara"))], away, PASS)


def test_move_the_player_to_a_hidden_location_reveals_it(state: GameState) -> None:
    events = resolve([Move(location_id=EntityId("vault"))], state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "moved"]
    discovered, moved = events
    assert isinstance(discovered, EntityDiscovered) and discovered.entity_id == "vault"
    assert isinstance(moved, Moved) and (moved.actor_id, moved.location_name) == (
        "player",
        "the vault",
    )


def test_move_the_player_to_a_known_location_does_not_rediscover(state: GameState) -> None:
    (moved,) = resolve([Move(location_id=EntityId("study"))], state, PASS)
    assert isinstance(moved, Moved) and moved.location_id == "study"


def test_move_a_known_actor_away_does_not_reveal(state: GameState) -> None:
    move = Move(location_id=EntityId("vault"), actor_id=EntityId("mara"))
    (moved,) = resolve([move], state, PASS)
    assert isinstance(moved, Moved) and (moved.actor_id, moved.location_id) == ("mara", "vault")


def test_move_a_hidden_actor_into_the_room_reveals_it(state: GameState) -> None:
    """Elena is hidden and at the player's location; moving her here reveals her arrival."""
    arrive = Move(location_id=EntityId("study"), actor_id=EntityId("elena"))
    events = resolve([arrive], state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "moved"]


def test_moving_an_actor_the_player_cannot_witness_fails(state: GameState) -> None:
    """With the player in the vault, a move touching only the study is off-screen: the resolver
    refuses it rather than narrating movement the player never saw."""
    in_vault = relocated(state, PLAYER_ID, EntityId("vault"))
    move = Move(location_id=EntityId("study"), actor_id=EntityId("mara"))
    with pytest.raises(ValueError, match="would not witness"):
        resolve([move], in_vault, PASS)


def test_a_consequence_used_on_the_wrong_kind_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="but it is a actor"):
        resolve([Move(location_id=EntityId("mara"))], state, PASS)
    with pytest.raises(ValueError, match="but it is a location"):
        resolve([TakeItem(item_id=EntityId("study"))], state, PASS)


def test_gain_loose_item_is_promoted_to_canon(state: GameState) -> None:
    events = resolve([GainImprovisedItem(item_name="a rusty key")], state, PASS)
    assert [e.type for e in events] == ["entity_created", "item_moved"]
    created, took = events
    assert isinstance(created, EntityCreated) and created.entity.name == "a rusty key"
    assert isinstance(took, ItemMoved) and took.item_id == created.entity.id


def test_discovering_a_known_entity_is_a_noop(state: GameState) -> None:
    assert resolve([Discover(entity_id=EntityId("mara"))], state, PASS) == []


def test_redundant_discover_then_take_reveals_once(state: GameState) -> None:
    vault_map = EntityId("vault_map")
    mechanics: list[Consequence] = [Discover(entity_id=vault_map), TakeItem(item_id=vault_map)]
    events = resolve(mechanics, state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "item_moved"]


def test_unknown_id_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        resolve([TakeItem(item_id=EntityId("ghost"))], state, PASS)


def test_roll_dice_binds_a_value_a_later_consequence_references(state: GameState) -> None:
    """A `roll_dice` total binds to a name; a nested `damage` reads it via Ref. '1d1' is
    deterministic, so the damage is exactly 1."""
    mechanics: list[Consequence] = [
        RollDice(dice="1d1", bind="dmg", then=[Damage(amount=Ref(ref="dmg"))])
    ]
    events = resolve(mechanics, state, PASS)
    assert [e.type for e in events] == ["dice_rolled", "hp_changed"]
    hp = events[1]
    assert isinstance(hp, HpChanged) and hp.delta == -1


def test_a_dangling_ref_raises_in_the_resolver(state: GameState) -> None:
    """The Director validator catches this first; the resolver is the backstop."""
    with pytest.raises(ValueError, match="never rolled"):
        resolve([Damage(amount=Ref(ref="nope"))], state, PASS)


def test_a_bind_made_inside_a_check_branch_does_not_leak_to_a_later_sibling(
    state: GameState,
) -> None:
    """The success branch binds `dmg`, but the bind closes with the branch; a later top-level
    `damage` cannot see it, so the resolver rejects the dangling ref instead of a stale value."""
    mechanics: list[Consequence] = [
        RollCheck(
            ability="wisdom", dc=12, on_success=[RollDice(dice="1d6", bind="dmg")]
        ),
        Damage(amount=Ref(ref="dmg")),
    ]
    with pytest.raises(ValueError, match="never rolled"):
        resolve(mechanics, state, PASS)
