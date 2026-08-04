from random import Random

import pytest
from core_test_support import updated, with_entity
from fivee_test_support import actor_of, blank_game, turn_of, with_actor
from fivee_test_support import state as state
from pydantic_ai import ModelRetry

from aidm.core.base import PLAYER_ID, EntityId
from aidm.core.world import GameState

# Kael's wisdom is 14 (+2). Random(0)'s first d20 is 13 (-> 15, passes DC 12); Random(2)'s is 2.
PASS, FAIL = Random(0), Random(2)


def relocated(state: GameState, entity_id: EntityId, location_id: EntityId) -> GameState:
    moved = updated(state.world.require(entity_id), parent_id=location_id)
    return with_entity(state, moved)


def test_heal_and_damage_clamp_and_report_only_real_change(state: GameState) -> None:
    """`delta` is what the clamp applies, not what was asked for: the Narrator must never be told
    of hit points that never moved, and a change of nothing is not a fact at all."""
    player = actor_of(state, PLAYER_ID)
    low_hp_state = with_actor(
        state, player.entity, updated(player.state, stats=updated(player.stats, hp=5))
    )
    hurt = turn_of(low_hp_state)
    (hp,) = hurt.call(hurt.tools.heal, amount=3)
    assert hp.data["delta"] == 3

    overkilled = turn_of(state)
    (overkill,) = overkilled.call(overkilled.tools.damage, amount=99)  # Kael has 10
    assert (overkill.data["delta"], overkill.data["wounds"]) == (-10, "down")
    healthy = turn_of(blank_game())
    assert healthy.call(healthy.tools.heal, amount=3) == []  # already at full health


def test_a_dice_amount_rolls_inside_the_change_it_pays_for(state: GameState) -> None:
    """The roll and the hit points it costs are one tool call — no value flows between two.
    '2d1' is deterministic, so the damage is exactly 2. A bare constant carries no die at all,
    so '4' and 4 must reach the Narrator as the same facts."""
    turn = turn_of(state)
    rolled, hp = turn.call(turn.tools.damage, amount="2d1")
    assert (rolled.kind, rolled.data["dice"]) == ("dice_rolled", "2d1")
    assert hp.data["delta"] == -2

    written = turn_of(blank_game())
    counted = turn_of(blank_game())
    assert written.call(written.tools.damage, amount="4") == counted.call(
        counted.tools.damage, amount=4
    )


def test_damage_reaches_only_an_actor_here_and_reveals_them_first(state: GameState) -> None:
    """Mara has 4 hp, so 3 damage leaves the event's concise wounds summary badly hurt. Elena is
    here but unrevealed, so damaging her must enter the player's view first."""
    turn = turn_of(state)
    (hp,) = turn.call(turn.tools.damage, amount=3, target_id=EntityId("mara"))
    assert (hp.data["target_id"], hp.data["delta"], hp.data["wounds"]) == ("mara", -3, "badly hurt")

    events = turn.call(turn.tools.damage, amount=1, target_id=EntityId("elena"))
    assert [e.kind for e in events] == ["entity_discovered", "hp_changed"]

    away = turn_of(relocated(state, EntityId("mara"), EntityId("vault")))
    with pytest.raises(ModelRetry, match="not here with the player"):
        _ = away.call(away.tools.damage, amount=1, target_id=EntityId("mara"))


def test_a_condition_takes_hold_lifts_and_is_not_reapplied(state: GameState) -> None:
    """Only a change is an event: a second helping of `prone` moved nothing, so the Narrator is not
    told it did."""
    turn = turn_of(state)
    (held,) = turn.call(turn.tools.apply_condition, condition="prone")
    assert (held.data["condition"], held.data["active"]) == ("prone", True)
    assert actor_of(turn.committed(), PLAYER_ID).stats.conditions == ("prone",)
    assert turn.call(turn.tools.apply_condition, condition="prone") == []
    (lifted,) = turn.call(turn.tools.apply_condition, condition="prone", ends=True)
    assert lifted.data["active"] is False
    assert actor_of(turn.committed(), PLAYER_ID).stats.conditions == ()


def test_an_immune_actor_is_simply_unaffected(state: GameState) -> None:
    """The rules decide, not the Director: it may name any condition and immunity absorbs it."""
    mara = actor_of(state, EntityId("mara"))
    immune = updated(mara.state, stats=updated(mara.stats, condition_immunities=("poisoned",)))
    unaffected = turn_of(with_actor(state, mara.entity, immune))
    poisoning: dict[str, object] = {"condition": "poisoned", "target_id": EntityId("mara")}
    assert unaffected.call(unaffected.tools.apply_condition, **poisoning) == []

    turn = turn_of(state)
    (changed,) = turn.call(turn.tools.apply_condition, **poisoning)
    assert changed.trace == "Mara is poisoned"


def test_a_roll_reports_its_outcome_instead_of_deciding_what_follows(state: GameState) -> None:
    """The point of the tool loop: the Director reads a real result before it acts on it."""
    passed = turn_of(state, PASS)
    (rolled,) = passed.call(passed.tools.roll_check, ability="wisdom", dc=12)
    assert rolled.data["success"] is True

    failed = turn_of(state, FAIL)
    (missed,) = failed.call(failed.tools.roll_check, ability="wisdom", dc=12)
    assert missed.data["success"] is False
