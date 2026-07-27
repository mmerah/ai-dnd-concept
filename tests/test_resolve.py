"""The resolver is the single sink from the Director's mechanics to events — pure, seeded.
The mechanics are a recursive consequence list: `roll_check` nests branches, and a dice amount
rolls inside the `damage`/`heal` that spends it. Positions gate take/drop/give/damage."""

from random import Random

import pytest

from aidm.domain.models import (
    PLAYER_ID,
    ActorEntity,
    ApplyCondition,
    CheckRolled,
    ConditionChanged,
    Consequence,
    Damage,
    DiceRolled,
    Discover,
    DropItem,
    Entity,
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
    RollCheck,
    TakeItem,
    updated,
)
from aidm.domain.reducer import apply
from aidm.engine.resolve import resolve

# Kael's wisdom is 14 (+2). Random(0)'s first d20 is 13 (-> 15, passes DC 12); Random(2)'s is 2.
PASS, FAIL = Random(0), Random(2)


def replaced(state: GameState, entity: Entity) -> GameState:
    entities = {**state.world.entities, entity.id: entity}
    return updated(state, world=updated(state.world, entities=entities))


def relocated(state: GameState, entity_id: EntityId, location_id: EntityId) -> GameState:
    return replaced(state, updated(state.world.entities[entity_id], location_id=location_id))


def wounded(state: GameState, hp: int) -> GameState:
    return replaced(state, updated(state.player, stats=updated(state.player.stats, hp=hp)))


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
    (hp,) = resolve([Heal(amount=3)], wounded(state, 5), PASS)
    assert isinstance(hp, HpChanged) and hp.delta == 3


def test_only_the_hit_points_that_moved_are_reported(state: GameState) -> None:
    """`delta` is what the clamp applies, not what was asked for: the Narrator must never be told
    of hit points that never moved, and a change of nothing is not an event at all."""
    (hp,) = resolve([Damage(amount=99)], state, PASS)  # Kael has 10
    assert isinstance(hp, HpChanged) and (hp.delta, hp.wounds) == (-10, "down")
    assert resolve([Heal(amount=3)], state, PASS) == []  # already at full health


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


def test_a_dice_amount_rolls_inside_the_change_it_pays_for(state: GameState) -> None:
    """The roll and the hit points it costs are one consequence — no value flows between two.
    '2d1' is deterministic, so the damage is exactly 2."""
    events = resolve([Damage(amount="2d1")], state, PASS)
    assert [e.type for e in events] == ["dice_rolled", "hp_changed"]
    rolled, hp = events
    assert isinstance(rolled, DiceRolled) and rolled.dice == "2d1"
    assert isinstance(hp, HpChanged) and hp.delta == -2


def test_a_constant_amount_carries_no_die(state: GameState) -> None:
    """'4' and 4 mean the same harm, so they must reach the Narrator as the same events."""
    assert resolve([Damage(amount="4")], state, PASS) == resolve([Damage(amount=4)], state, PASS)


def test_damage_can_target_another_actor_here(state: GameState) -> None:
    """Mara has the commoner's 4 hp, so 3 leaves her badly hurt — the qualitative report the
    Narrator gets instead of her exact hit points."""
    events = resolve([Damage(amount=3, target_id=EntityId("mara"))], state, PASS)
    (hp,) = events
    assert isinstance(hp, HpChanged)
    assert (hp.target_id, hp.delta, hp.wounds) == ("mara", -3, "badly hurt")


def test_damaging_an_unseen_actor_reveals_them_first(state: GameState) -> None:
    """Elena is here but unrevealed; the events name her, so she must enter the player's view."""
    events = resolve([Damage(amount=1, target_id=EntityId("elena"))], state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "hp_changed"]


def test_damaging_an_actor_elsewhere_fails(state: GameState) -> None:
    away = relocated(state, EntityId("mara"), EntityId("vault"))
    with pytest.raises(ValueError, match="not at the player's location"):
        resolve([Damage(amount=1, target_id=EntityId("mara"))], away, PASS)


def test_a_condition_takes_hold_lifts_and_is_not_reapplied(state: GameState) -> None:
    """Only a change is an event: a second helping of `prone` moved nothing, so the Narrator is not
    told it did."""
    prone = ApplyCondition(condition="prone")
    (held,) = resolve([prone], state, PASS)
    assert isinstance(held, ConditionChanged) and (held.condition, held.active) == ("prone", True)
    after = apply(state, [held])
    assert after.player.stats.conditions == ("prone",)
    assert resolve([prone], after, PASS) == []
    (lifted,) = resolve([updated(prone, ends=True)], after, PASS)
    assert isinstance(lifted, ConditionChanged) and not lifted.active
    assert apply(after, [lifted]).player.stats.conditions == ()


def test_an_immune_actor_is_simply_unaffected(state: GameState) -> None:
    """The rules decide, not the Director: it may name any condition and immunity absorbs it."""
    mara = state.world.entities[EntityId("mara")]
    assert isinstance(mara, ActorEntity)
    immune = updated(mara, stats=updated(mara.stats, condition_immunities=("poisoned",)))
    poisoned = ApplyCondition(condition="poisoned", target_id=EntityId("mara"))
    assert resolve([poisoned], replaced(state, immune), PASS) == []
    (changed,) = resolve([poisoned], state, PASS)
    assert isinstance(changed, ConditionChanged) and changed.summary == "Mara is poisoned"
