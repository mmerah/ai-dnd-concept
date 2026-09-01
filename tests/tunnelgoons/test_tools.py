import re
from random import Random

import pytest
from tunnelgoons_test_support import (
    CRYPT,
    HALL,
    KEY,
    LANTERN,
    MANTIS,
    MIRA,
    ROPE,
    START,
    VAULT,
    changed,
    refused,
    small_world,
)

from aidm.core.entities import EntityId
from aidm.core.tools import NoArgs
from aidm.engines.core import PLAYER_ID
from aidm.engines.tunnelgoons.tools import (
    ActionRoll,
    LevelUp,
    Move,
    UnlockWay,
    action_roll,
    level_up,
    move,
    rest,
    unlock_way,
)
from aidm.engines.tunnelgoons.world import Item, Visit, player_over

TOTAL_RE = re.compile(r"(-?\d+) vs DS")


def _total(card: str) -> int:
    match = TOTAL_RE.search(card)
    assert match is not None
    return int(match.group(1))


def test_the_roll_adds_ability_and_items_and_penalizes_brute_and_skulker_over_inventory() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.player.skulker = 2
    world.player.inventory = 1  # carrying rope + torch (2) is 1 over
    facts = action_roll(
        draft,
        ActionRoll(what="Sneak past", ability="skulker", items=(ROPE,), difficulty=10),
        Random(1),
    )
    rolled = next(fact for fact in facts if fact.kind == "action_rolled")
    dice = rolled.dice[0].rolled
    assert _total(rolled.card) == sum(dice) + world.player.skulker + 1 - 1


def test_erudite_rolls_are_not_penalized_for_over_inventory() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.player.erudite = 2
    world.player.inventory = 1
    facts = action_roll(
        draft, ActionRoll(what="Read the runes", ability="erudite", difficulty=8), Random(2)
    )
    rolled = next(fact for fact in facts if fact.kind == "action_rolled")
    dice = rolled.dice[0].rolled
    assert _total(rolled.card) == sum(dice) + world.player.erudite


def test_a_roll_against_an_npc_that_hits_can_slay_it() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.npcs[MANTIS].place = START
    world.player.brute = 10  # min total 12 always beats DS 4
    facts = action_roll(
        draft,
        ActionRoll(what="Smash it", ability="brute", against=MANTIS, dangerous=True),
        Random(3),
    )
    mantis = world.npcs[MANTIS]
    assert mantis.hp.current == 0
    assert not mantis.alive
    assert any(fact.kind == "npc_slain" for fact in facts)


def test_a_miss_against_an_npc_can_kill_the_player() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.npcs[MANTIS].place = START
    world.npcs[MANTIS].hp.maximum = 20
    world.npcs[MANTIS].hp.current = 20  # max total 12 never beats DS 20
    world.player.brute = 0
    world.player.hp.current = 1
    facts = action_roll(
        draft,
        ActionRoll(what="Smash it", ability="brute", against=MANTIS, dangerous=True),
        Random(4),
    )
    assert world.player.hp.current == 0
    assert not world.player.alive
    assert player_over(draft) == "You died."
    assert any(fact.kind == "goon_killed" for fact in facts)


def test_a_roll_against_an_npc_wounds_nobody_unless_it_is_dangerous() -> None:
    """SRD: only a dangerous action turns the margin into damage; talk against a DS does not."""
    draft = small_world().draft()
    world = draft.payload.world
    world.npcs[MANTIS].place = START
    facts = action_roll(
        draft, ActionRoll(what="Talk it down", ability="erudite", against=MANTIS), Random(3)
    )
    assert world.npcs[MANTIS].hp.current == world.npcs[MANTIS].hp.maximum
    assert world.player.hp.current == world.player.hp.maximum
    assert not any(fact.kind == "counter_changed" for fact in facts)


def test_dangerous_hurts_only_on_a_miss() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.player.erudite = 12  # min total 14 always beats DS 8
    before = world.player.hp.current
    facts = action_roll(
        draft,
        ActionRoll(what="Cross the gap", ability="erudite", difficulty=8, dangerous=True),
        Random(0),
    )
    assert world.player.hp.current == before
    assert not any(fact.kind == "counter_changed" for fact in facts)

    draft2 = small_world().draft()
    world2 = draft2.payload.world
    world2.player.inventory = 0
    world2.items.update(
        {
            EntityId(f"junk-{n}"): Item(
                id=EntityId(f"junk-{n}"),
                name=f"Junk {n}",
                brief="Clutter",
                known=True,
                on=PLAYER_ID,
            )
            for n in range(11)
        }
    )  # carried (13) - inventory (0) = 13 penalty, always below any legal DS
    facts2 = action_roll(
        draft2,
        ActionRoll(what="Cross the gap", ability="brute", difficulty=8, dangerous=True),
        Random(0),
    )
    assert world2.player.hp.current < world2.player.hp.maximum
    assert any(fact.kind == "counter_changed" for fact in facts2)


def test_neither_or_both_of_difficulty_and_against_is_refused() -> None:
    with pytest.raises(ValueError, match="not both/neither"):
        ActionRoll(what="Push", ability="brute")
    with pytest.raises(ValueError, match="not both/neither"):
        ActionRoll(what="Push", ability="brute", difficulty=8, against=MANTIS)


def test_an_item_not_in_the_players_hands_is_refused() -> None:
    draft = small_world().draft()
    with pytest.raises(ValueError, match="not in the player's hands"):
        _ = action_roll(
            draft,
            ActionRoll(what="Pick lock", ability="skulker", items=(KEY,), difficulty=8),
            Random(0),
        )


def test_rest_heals_the_player() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.player.hp.current = 4
    facts = rest(draft, NoArgs(), Random(0))
    assert world.player.hp.current == world.player.hp.maximum
    assert any(fact.kind == "rested" for fact in facts)


def test_level_up_with_no_args_opens_the_six_option_decision() -> None:
    draft = small_world().draft()
    facts = level_up(draft, LevelUp(), Random(0))
    assert facts == []
    assert draft.pending is not None
    assert len(draft.pending.options) == 6


def test_level_up_with_both_raises_the_ability_and_the_boost_and_the_level() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    before = world.player.level
    facts = level_up(draft, LevelUp(ability="brute", boost="health"), Random(0))
    assert world.player.brute == 2
    assert world.player.level == before + 1
    assert any(fact.kind == "levelled_up" for fact in facts)


def test_level_up_with_one_argument_is_refused() -> None:
    draft = small_world().draft()
    with pytest.raises(ValueError, match="takes both"):
        _ = level_up(draft, LevelUp(ability="brute"), Random(0))


def test_move_refuses_a_locked_way() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.player.place = HALL
    world.visits.append(Visit(place=HALL))
    with pytest.raises(ValueError, match="locked"):
        _ = move(draft, Move(to_id=VAULT), Random(0))


def test_move_refuses_when_there_is_no_way() -> None:
    draft = small_world().draft()
    with pytest.raises(ValueError, match="no way leads"):
        _ = move(draft, Move(to_id=CRYPT), Random(0))


def test_move_reveals_the_destination_and_adds_a_visit() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    before = len(world.visits)
    facts = move(draft, Move(to_id=VAULT), Random(0))
    assert world.player.place == VAULT
    assert world.places[VAULT].known
    assert len(world.visits) == before + 1
    assert any(fact.kind == "arrived" for fact in facts)


def test_move_with_ids_brings_an_npc_here_and_refuses_one_standing_elsewhere() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    facts = move(draft, Move(to_id=VAULT, with_ids=(MIRA,)), Random(0))
    assert world.npcs[MIRA].place == VAULT
    assert any("Mira" in fact.trace for fact in facts if fact.kind == "arrived")

    elsewhere = small_world().draft()
    with pytest.raises(ValueError, match="not here"):
        _ = move(elsewhere, Move(to_id=VAULT, with_ids=(MANTIS,)), Random(0))


def test_unlock_way_then_move_passes() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.player.place = HALL
    world.visits.append(Visit(place=HALL))
    _ = unlock_way(draft, UnlockWay(to_id=VAULT), Random(0))
    facts = move(draft, Move(to_id=VAULT), Random(0))
    assert world.player.place == VAULT
    assert any(fact.kind == "arrived" for fact in facts)


def test_move_item_to_the_player_to_an_npc_here_and_to_the_place() -> None:
    draft = small_world().draft()
    world = draft.payload.world

    _ = changed(draft, "move_item", item_id=LANTERN, to=MIRA)
    assert world.items[LANTERN].on == MIRA

    _ = changed(draft, "move_item", item_id=LANTERN, to=PLAYER_ID)
    assert world.items[LANTERN].on == PLAYER_ID

    _ = changed(draft, "move_item", item_id=LANTERN, to=START)
    assert world.items[LANTERN].on == START


def test_move_item_refuses_a_holder_the_player_has_not_met() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    world.npcs[MANTIS].place = START
    with pytest.raises(ValueError, match="has not met"):
        _ = changed(draft, "move_item", item_id=LANTERN, to=MANTIS)


def test_kill_drops_an_npcs_items_loose() -> None:
    draft = small_world().draft()
    world = draft.payload.world
    blade = EntityId("mira-blade")
    world.items[blade] = Item(id=blade, name="Blade", brief="Mira's blade", known=True, on=MIRA)

    _ = changed(draft, "kill", entity_id=MIRA)

    assert not world.npcs[MIRA].alive
    assert world.items[blade].on == START


def test_reveal_only_what_is_here_and_unknown() -> None:
    draft = small_world().draft()
    world = draft.payload.world

    assert "not here" in refused(draft, "reveal", entity_id=KEY)
    assert "already" in refused(draft, "reveal", entity_id=LANTERN)

    world.npcs[MANTIS].place = START
    _ = changed(draft, "reveal", entity_id=MANTIS)
    assert world.npcs[MANTIS].known
