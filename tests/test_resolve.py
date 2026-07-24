"""The resolver is the single sink from the Director's mechanics to events — pure, seeded."""

from random import Random

import pytest

from aidm.domain.models import (
    Check,
    CheckRolled,
    Discover,
    EntityDiscovered,
    EntityId,
    GainImprovisedItem,
    GainItem,
    GameState,
    InventoryChanged,
    LoseItem,
    Mechanics,
    ModifyHp,
    Move,
    Moved,
)
from aidm.engine.resolve import resolve

# Kael's wisdom is 14 (+2). Random(0)'s first d20 is 13 (-> 15, passes DC 12); Random(2)'s is 2.
PASS, FAIL = Random(0), Random(2)


def test_no_check_applies_unconditional_then_success_branch(state: GameState) -> None:
    mechanics = Mechanics(
        unconditional=[ModifyHp(delta=-2)],
        on_success=[Move(location_id=EntityId("vault"))],
        on_failure=[Move(location_id=EntityId("study"))],
    )
    events = resolve(mechanics, state, PASS)
    assert [e.type for e in events] == ["hp_changed", "entity_discovered", "moved"]
    moved = events[2]
    assert isinstance(moved, Moved) and moved.entity_id == "vault"  # no check -> success


def test_check_success_selects_on_success(state: GameState) -> None:
    mechanics = Mechanics(
        check=Check(ability="wisdom", dc=12),
        on_success=[GainImprovisedItem(item_name="a torch")],
        on_failure=[ModifyHp(delta=-5)],
    )
    events = resolve(mechanics, state, PASS)
    assert [e.type for e in events] == ["check_rolled", "inventory_changed"]
    rolled = events[0]
    assert isinstance(rolled, CheckRolled) and rolled.success


def test_check_failure_selects_on_failure(state: GameState) -> None:
    mechanics = Mechanics(
        check=Check(ability="wisdom", dc=12),
        on_success=[GainImprovisedItem(item_name="a torch")],
        on_failure=[ModifyHp(delta=-5)],
    )
    events = resolve(mechanics, state, FAIL)
    assert [e.type for e in events] == ["check_rolled", "hp_changed"]
    rolled = events[0]
    assert isinstance(rolled, CheckRolled) and not rolled.success


def test_gain_canon_item_reveals_hidden_and_stores_the_name(state: GameState) -> None:
    events = resolve(Mechanics(on_success=[GainItem(item_id=EntityId("vault_map"))]), state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "inventory_changed"]
    gained = events[1]
    assert isinstance(gained, InventoryChanged)
    assert gained.item == "the vault map" and gained.delta == 1  # canonical name, not the id


def test_move_to_a_hidden_location_reveals_it_on_arrival(state: GameState) -> None:
    events = resolve(Mechanics(on_success=[Move(location_id=EntityId("vault"))]), state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "moved"]
    discovered, moved = events
    assert isinstance(discovered, EntityDiscovered) and discovered.entity_id == "vault"
    # the id drives state; the name rides along so the Narrator's summary never shows an id
    assert isinstance(moved, Moved) and (moved.entity_id, moved.name) == ("vault", "the vault")


def test_move_to_a_known_location_does_not_rediscover(state: GameState) -> None:
    events = resolve(Mechanics(on_success=[Move(location_id=EntityId("study"))]), state, PASS)
    (moved,) = events
    assert isinstance(moved, Moved) and moved.entity_id == "study"


def test_a_consequence_used_on_the_wrong_kind_raises(state: GameState) -> None:
    """Naming an npc where a location belongs is a broken invariant, not a silent coercion."""
    with pytest.raises(ValueError, match="but it is a npc"):
        resolve(Mechanics(on_success=[Move(location_id=EntityId("mara"))]), state, PASS)
    with pytest.raises(ValueError, match="but it is a location"):
        resolve(Mechanics(on_success=[GainItem(item_id=EntityId("study"))]), state, PASS)


def test_gain_loose_item_is_stored_verbatim(state: GameState) -> None:
    mechanics = Mechanics(on_success=[GainImprovisedItem(item_name="a rusty key")])
    events = resolve(mechanics, state, PASS)
    (gained,) = events
    assert isinstance(gained, InventoryChanged) and gained.item == "a rusty key"


def test_lose_canon_item_canonicalizes_against_the_draft(state: GameState) -> None:
    """Gaining then losing the same canon item folds through the draft: the lose sees the gained
    name in inventory, and both events canonicalize the id to `entity.name`."""
    vault_map = EntityId("vault_map")
    mechanics = Mechanics(unconditional=[GainItem(item_id=vault_map), LoseItem(item_id=vault_map)])
    events = resolve(mechanics, state, PASS)
    kinds = [e.type for e in events]
    assert kinds == ["entity_discovered", "inventory_changed", "inventory_changed"]
    lost = events[2]
    assert isinstance(lost, InventoryChanged) and (lost.item, lost.delta) == ("the vault map", -1)


def test_discovering_a_known_entity_is_a_noop(state: GameState) -> None:
    assert resolve(Mechanics(on_success=[Discover(entity_id=EntityId("mara"))]), state, PASS) == []


def test_redundant_discover_then_gain_reveals_once(state: GameState) -> None:
    """A plan may reveal an entity and gain it as an item; the second reveal must no-op against the
    draft-so-far, not re-emit EntityDiscovered."""
    vault_map = EntityId("vault_map")
    mechanics = Mechanics(on_success=[Discover(entity_id=vault_map), GainItem(item_id=vault_map)])
    events = resolve(mechanics, state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "inventory_changed"]


def test_unknown_id_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        resolve(Mechanics(on_success=[GainItem(item_id=EntityId("ghost"))]), state, PASS)
