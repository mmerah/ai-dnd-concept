"""The resolver is the single sink from the Director's plan to events — pure, seeded, branchy."""

from random import Random

import pytest

from aidm.domain.events import CheckRolled, InventoryChanged, Moved
from aidm.domain.models import (
    Check,
    Discover,
    EntityId,
    GainCanonItem,
    GainLooseItem,
    GameState,
    LoseCanonItem,
    ModifyHp,
    Move,
    Plan,
)
from aidm.engine.resolve import resolve

# Kael's wisdom is 14 (+2). Random(0)'s first d20 is 13 (-> 15, passes DC 12); Random(2)'s is 2.
PASS, FAIL = Random(0), Random(2)


def test_no_check_applies_unconditional_then_success_branch(state: GameState) -> None:
    plan = Plan(
        unconditional=[ModifyHp(delta=-2)],
        on_success=[Move(location="the vault")],
        on_failure=[Move(location="the cell")],
    )
    events = resolve(plan, state, PASS)
    assert [e.type for e in events] == ["hp_changed", "moved"]
    moved = events[1]
    assert isinstance(moved, Moved) and moved.location == "the vault"  # no check -> success


def test_check_success_selects_on_success(state: GameState) -> None:
    plan = Plan(
        check=Check(ability="wisdom", dc=12),
        on_success=[GainLooseItem(item="a torch")],
        on_failure=[ModifyHp(delta=-5)],
    )
    events = resolve(plan, state, PASS)
    assert [e.type for e in events] == ["check_rolled", "inventory_changed"]
    rolled = events[0]
    assert isinstance(rolled, CheckRolled) and rolled.success


def test_check_failure_selects_on_failure(state: GameState) -> None:
    plan = Plan(
        check=Check(ability="wisdom", dc=12),
        on_success=[GainLooseItem(item="a torch")],
        on_failure=[ModifyHp(delta=-5)],
    )
    events = resolve(plan, state, FAIL)
    assert [e.type for e in events] == ["check_rolled", "hp_changed"]
    rolled = events[0]
    assert isinstance(rolled, CheckRolled) and not rolled.success


def test_gain_canon_item_reveals_hidden_and_stores_the_name(state: GameState) -> None:
    events = resolve(Plan(on_success=[GainCanonItem(entity_id=EntityId("vault_map"))]), state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "inventory_changed"]
    gained = events[1]
    assert isinstance(gained, InventoryChanged)
    assert gained.item == "the vault map" and gained.delta == 1  # canonical name, not the id


def test_gain_loose_item_is_stored_verbatim(state: GameState) -> None:
    events = resolve(Plan(on_success=[GainLooseItem(item="a rusty key")]), state, PASS)
    (gained,) = events
    assert isinstance(gained, InventoryChanged) and gained.item == "a rusty key"


def test_lose_canon_item_canonicalizes_against_the_draft(state: GameState) -> None:
    """Gaining then losing the same canon item folds through the draft: the lose sees the gained
    name in inventory, and both events canonicalize the id to `entity.name`."""
    vault_map = EntityId("vault_map")
    plan = Plan(
        unconditional=[GainCanonItem(entity_id=vault_map), LoseCanonItem(entity_id=vault_map)]
    )
    events = resolve(plan, state, PASS)
    kinds = [e.type for e in events]
    assert kinds == ["entity_discovered", "inventory_changed", "inventory_changed"]
    lost = events[2]
    assert isinstance(lost, InventoryChanged) and (lost.item, lost.delta) == ("the vault map", -1)


def test_discovering_a_known_entity_is_a_noop(state: GameState) -> None:
    assert resolve(Plan(on_success=[Discover(entity_id=EntityId("mara"))]), state, PASS) == []


def test_redundant_discover_then_gain_reveals_once(state: GameState) -> None:
    """A plan may reveal an entity and gain it as an item; the second reveal must no-op against the
    draft-so-far, not re-emit EntityDiscovered."""
    vault_map = EntityId("vault_map")
    plan = Plan(on_success=[Discover(entity_id=vault_map), GainCanonItem(entity_id=vault_map)])
    events = resolve(plan, state, PASS)
    assert [e.type for e in events] == ["entity_discovered", "inventory_changed"]


def test_unknown_id_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        resolve(Plan(on_success=[GainCanonItem(entity_id=EntityId("ghost"))]), state, PASS)
