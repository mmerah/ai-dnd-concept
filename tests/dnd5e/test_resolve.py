from random import Random

import pytest
from core_test_support import updated, with_entity
from fivee_test_support import actor_of, blank_game, ruleset, with_actor
from fivee_test_support import state as state

from aidm.base import PLAYER_ID, EntityId
from aidm.engines.dnd5e.access import Dnd5eWorld
from aidm.engines.dnd5e.direction import (
    ApplyCondition,
    Consequence,
    Damage,
    Discover,
    DropItem,
    GainImprovisedItem,
    GiveItem,
    Heal,
    Move,
    RollCheck,
    TakeItem,
)
from aidm.engines.dnd5e.resolve import resolve as _resolve
from aidm.facts import Fact
from aidm.world import GameState

RULES = ruleset()  # `attack` reads a weapon profile and an archetype's own attack out of it

# Kael's wisdom is 14 (+2). Random(0)'s first d20 is 13 (-> 15, passes DC 12); Random(2)'s is 2.
PASS, FAIL = Random(0), Random(2)


def resolve(mechanics: list[Consequence], state: GameState, rng: Random = PASS) -> list[Fact]:
    """Commit so a later call in the same test sees an earlier call's typed-state mutation."""
    world = Dnd5eWorld(state=state)
    facts = _resolve(mechanics, world, rng, RULES)
    _ = world.commit()
    return facts


def relocated(state: GameState, entity_id: EntityId, location_id: EntityId) -> GameState:
    moved = updated(state.world.require(entity_id), location_id=location_id)
    return with_entity(state, moved)


def test_top_level_consequences_all_apply_in_order(state: GameState) -> None:
    events = resolve([Damage(amount=2), Move(location_id=EntityId("vault"))], state)
    assert [e.kind for e in events] == ["hp_changed", "entity_discovered", "actor_moved"]
    hp, moved = events[0], events[2]
    assert hp.data["delta"] == -2
    assert (moved.data["actor_id"], moved.data["location_id"]) == ("player", "vault")


def test_check_selects_the_branch_the_roll_decides(state: GameState) -> None:
    mechanics: list[Consequence] = [
        RollCheck(
            ability="wisdom",
            dc=12,
            on_success=[GainImprovisedItem(item_name="a torch")],
            on_failure=[Damage(amount=5)],
        )
    ]
    passed = resolve(mechanics, state, PASS)
    # improvised gain promotes the item to canon first, then adds it to inventory
    assert [e.kind for e in passed] == ["dc_rolled", "entity_created", "item_moved"]
    assert passed[0].data["success"] is True
    assert passed[1].data["name"] == "a torch"

    failed = resolve(mechanics, state, FAIL)
    assert [e.kind for e in failed] == ["dc_rolled", "hp_changed"]
    assert failed[0].data["success"] is False
    assert failed[1].data["delta"] == -5


def test_heal_and_damage_clamp_and_report_only_real_change(state: GameState) -> None:
    """`delta` is what the clamp applies, not what was asked for: the Narrator must never be told
    of hit points that never moved, and a change of nothing is not a fact at all."""
    player = actor_of(state, PLAYER_ID)
    low_hp_state = with_actor(
        state, player.entity, updated(player.state, stats=updated(player.stats, hp=5))
    )
    (hp,) = resolve([Heal(amount=3)], low_hp_state)
    assert hp.data["delta"] == 3

    (overkill,) = resolve([Damage(amount=99)], state)  # Kael has 10
    assert (overkill.data["delta"], overkill.data["wounds"]) == (-10, "down")
    assert resolve([Heal(amount=3)], blank_game()) == []  # already at full health


def test_take_gates_on_position(state: GameState) -> None:
    took = resolve([TakeItem(item_id=EntityId("vault_map"))], state)[1]
    assert (took.data["item_id"], took.data["to_id"]) == ("vault_map", PLAYER_ID)
    with pytest.raises(ValueError, match="not at the player's location"):
        resolve([TakeItem(item_id=EntityId("lantern"))], state)  # carried, not lying here


def test_drop_gates_on_carrying(state: GameState) -> None:
    (dropped,) = resolve([DropItem(item_id=EntityId("lantern"))], state)
    assert (dropped.data["item_id"], dropped.data["to_kind"]) == ("lantern", "location")
    with pytest.raises(ValueError, match="not carrying"):
        resolve([DropItem(item_id=EntityId("vault_map"))], state)


def test_give_gates_on_carrying_and_the_recipients_position(state: GameState) -> None:
    with pytest.raises(ValueError, match="already hold it"):
        resolve(
            [GiveItem(item_id=EntityId("lantern"), actor_id=PLAYER_ID)], state.model_copy(deep=True)
        )
    away = relocated(state, EntityId("mara"), EntityId("vault"))
    with pytest.raises(ValueError, match="not at the player's location"):
        resolve([GiveItem(item_id=EntityId("lantern"), actor_id=EntityId("mara"))], away)

    (given,) = resolve([GiveItem(item_id=EntityId("lantern"), actor_id=EntityId("mara"))], state)
    assert (given.data["item_id"], given.data["to_id"]) == ("lantern", "mara")


def test_move_the_player_reveals_only_a_hidden_destination(state: GameState) -> None:
    hidden = resolve([Move(location_id=EntityId("vault"))], state.model_copy(deep=True))
    assert [e.kind for e in hidden] == ["entity_discovered", "actor_moved"]
    (known,) = resolve([Move(location_id=EntityId("study"))], state)
    assert known.data["location_id"] == "study"


def test_moving_another_actor_reveals_only_if_the_player_witnesses_it(state: GameState) -> None:
    known = resolve(
        [Move(location_id=EntityId("vault"), actor_id=EntityId("mara"))],
        state.model_copy(deep=True),
    )
    assert known[0].data["actor_id"] == "mara"
    hidden = resolve([Move(location_id=EntityId("study"), actor_id=EntityId("elena"))], state)
    assert [e.kind for e in hidden] == ["entity_discovered", "actor_moved"]

    in_vault = relocated(state, PLAYER_ID, EntityId("vault"))
    with pytest.raises(ValueError, match="would not witness"):
        resolve([Move(location_id=EntityId("study"), actor_id=EntityId("mara"))], in_vault)


def test_a_consequence_used_on_the_wrong_kind_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="but it is a actor"):
        resolve([Move(location_id=EntityId("mara"))], state)
    with pytest.raises(ValueError, match="but it is a location"):
        resolve([TakeItem(item_id=EntityId("study"))], state)


def test_gain_loose_item_is_promoted_to_canon(state: GameState) -> None:
    created, took = resolve([GainImprovisedItem(item_name="a rusty key")], state)
    assert created.data["name"] == "a rusty key"
    assert took.data["item_id"] == created.data["entity_id"]


def test_discover_is_idempotent_and_composes_with_take(state: GameState) -> None:
    assert resolve([Discover(entity_id=EntityId("mara"))], state) == []

    vault_map = EntityId("vault_map")
    events = resolve([Discover(entity_id=vault_map), TakeItem(item_id=vault_map)], state)
    assert [e.kind for e in events] == ["entity_discovered", "item_moved"]


def test_unknown_id_raises(state: GameState) -> None:
    with pytest.raises(ValueError, match="unknown entity id"):
        resolve([TakeItem(item_id=EntityId("ghost"))], state)


def test_a_dice_amount_rolls_inside_the_change_it_pays_for(state: GameState) -> None:
    """The roll and the hit points it costs are one consequence — no value flows between two.
    '2d1' is deterministic, so the damage is exactly 2. A bare constant carries no die at all,
    so '4' and 4 must reach the Narrator as the same facts."""
    rolled, hp = resolve([Damage(amount="2d1")], state)
    assert (rolled.kind, rolled.data["dice"]) == ("dice_rolled", "2d1")
    assert hp.data["delta"] == -2
    assert resolve([Damage(amount="4")], blank_game()) == resolve([Damage(amount=4)], blank_game())


def test_damage_can_target_another_actor_here_and_reveals_them_first(state: GameState) -> None:
    """Mara has 4 hp, so 3 damage leaves the event's concise wounds summary badly hurt. Elena is
    here but unrevealed, so damaging her must enter the player's view first."""
    (hp,) = resolve([Damage(amount=3, target_id=EntityId("mara"))], state)
    assert (hp.data["target_id"], hp.data["delta"], hp.data["wounds"]) == ("mara", -3, "badly hurt")

    events = resolve([Damage(amount=1, target_id=EntityId("elena"))], state)
    assert [e.kind for e in events] == ["entity_discovered", "hp_changed"]


def test_damaging_an_actor_elsewhere_fails(state: GameState) -> None:
    away = relocated(state, EntityId("mara"), EntityId("vault"))
    with pytest.raises(ValueError, match="not at the player's location"):
        resolve([Damage(amount=1, target_id=EntityId("mara"))], away)


def test_a_condition_takes_hold_lifts_and_is_not_reapplied(state: GameState) -> None:
    """Only a change is an event: a second helping of `prone` moved nothing, so the Narrator is not
    told it did."""
    prone = ApplyCondition(condition="prone")
    (held,) = resolve([prone], state)
    assert (held.data["condition"], held.data["active"]) == ("prone", True)
    assert actor_of(state, PLAYER_ID).stats.conditions == ("prone",)
    assert resolve([prone], state) == []
    (lifted,) = resolve([updated(prone, ends=True)], state)
    assert lifted.data["active"] is False
    assert actor_of(state, PLAYER_ID).stats.conditions == ()


def test_an_immune_actor_is_simply_unaffected(state: GameState) -> None:
    """The rules decide, not the Director: it may name any condition and immunity absorbs it."""
    mara = actor_of(state, EntityId("mara"))
    immune = updated(mara.state, stats=updated(mara.stats, condition_immunities=("poisoned",)))
    poisoned = ApplyCondition(condition="poisoned", target_id=EntityId("mara"))
    assert resolve([poisoned], with_actor(state, mara.entity, immune)) == []
    (changed,) = resolve([poisoned], state)
    assert changed.trace == "Mara is poisoned"
