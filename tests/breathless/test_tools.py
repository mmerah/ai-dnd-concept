from random import Random

import pytest
from support.breathless import MIRA, WRENCH, hired, small_world
from support.table import change, refused

from aidm.core.entities import EntityId, Refusal
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.breathless.tools import Actor, Check, LootCheck
from aidm.engines.breathless.tools import TestLuck as LuckTest
from aidm.engines.breathless.world import Item, stepped
from aidm.engines.scenes.tools import NextScene
from aidm.engines.scenes.world import SCENE_LEFT

ENGINE = BreathlessEngine()


def test_check_on_a_skill_wears_it() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.roll(draft, Check(what="Force the door", skill="bash"), Random(0))
    assert player.dice().worn["bash"] == stepped(6)
    assert any(fact.kind == "checked" for fact in facts)


def test_check_at_d4_stays_d4() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = ENGINE.roll(draft, Check(what="Spot a way through", skill="dash"), Random(1))
    assert player.dice().worn["dash"] == 4


def test_an_item_reduced_to_d4_is_gone() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.dice().items[WRENCH].die = 6
    facts = ENGINE.roll(draft, Check(what="Swing the axe", item_id=WRENCH), Random(0))
    assert WRENCH not in player.dice().items
    assert any(fact.kind == "item_gone" for fact in facts)


def test_stunt_refused_twice() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = ENGINE.roll(draft, Check(what="Leap the gap", stunt=True), Random(0))
    assert player.dice().stunted
    with pytest.raises(Refusal, match="catches their breath"):
        _ = ENGINE.roll(draft, Check(what="Leap again", stunt=True), Random(0))


def test_check_with_actor_id_rolls_and_wears_the_members_die() -> None:
    draft = small_world().draft()
    member = hired(draft.payload, MIRA)
    facts = ENGINE.roll(draft, Check(what="Slip past", skill="sneak", actor_id=MIRA), Random(0))
    assert member.dice().worn["sneak"] == stepped(8)
    assert any(fact.kind == "checked" and "Mira" in fact.trace for fact in facts)


def test_check_with_helped_by_keeps_the_highest_and_wears_both_dice() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    member = hired(draft.payload, MIRA)
    facts = ENGINE.roll(
        draft, Check(what="Force the door", skill="bash", helped_by=MIRA), Random(0)
    )
    assert player.dice().worn["bash"] == stepped(6)
    assert member.dice().worn["bash"] == stepped(6)
    assert any(fact.kind == "checked" and "helped by Mira" in fact.trace for fact in facts)


def test_check_needs_exactly_one_of_skill_item_or_stunt() -> None:
    with pytest.raises(ValueError, match="roll one thing"):
        Check(what="Do something")
    with pytest.raises(ValueError, match="roll one thing"):
        Check(what="Do something", skill="bash", stunt=True)


def test_helped_by_refused_on_an_item_or_stunt_check() -> None:
    with pytest.raises(ValueError, match="help joins a skill check"):
        Check(what="Swing the axe", item_id=WRENCH, helped_by=MIRA)


def test_vulnerable_fail_leaves_a_note() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.dice().stress.current = 4
    _ = ENGINE.roll(draft, Check(what="Force the door", skill="bash", dangerous=True), Random(2))
    assert any("vulnerable" in note for note in draft.notes)


def test_catch_breath_resets_worn_loot_and_stunt_but_keeps_stress_and_item_dice() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    sheet = player.dice()
    sheet.worn["bash"] = 4
    sheet.loot = 6
    sheet.stunted = True
    sheet.stress.current = 2
    sheet.items[WRENCH].die = 6

    facts = ENGINE.catch_breath(draft, Actor(), Random(0))

    assert sheet.worn == sheet.skills
    assert sheet.loot == 12
    assert not sheet.stunted
    assert sheet.stress.current == 2
    assert sheet.items[WRENCH].die == 6
    assert any("The SRD's table suggests" in note for note in draft.notes)
    assert {fact.kind for fact in facts} == {"dice_rolled", "breath_caught"}
    assert next(f for f in facts if f.kind == "breath_caught").card == (
        "Caught breath — skills and loot die restored"
    )


def test_catch_breath_with_actor_id_resets_only_the_members_sheet() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    member = hired(draft.payload, MIRA)
    player.dice().worn["bash"] = 4
    member.dice().worn["bash"] = 4

    _ = ENGINE.catch_breath(draft, Actor(actor_id=MIRA), Random(0))

    assert member.dice().worn["bash"] == member.dice().skills["bash"]
    assert player.dice().worn["bash"] == 4


def test_use_med_kit_refused_without_a_kit() -> None:
    draft = small_world().draft()
    assert "holds no med kit" in refused(ENGINE, draft, "use_med_kit")


def test_use_med_kit_clears_two_stress() -> None:
    draft = small_world().draft()
    sheet = draft.payload.player.dice()
    sheet.med_kit = True
    sheet.stress.current = 3
    facts = change(ENGINE, draft, "use_med_kit")
    assert not sheet.med_kit
    assert sheet.stress.current == 1
    assert any(fact.kind == "med_kit_used" for fact in facts)


def test_change_stress_refuses_a_zero_amount() -> None:
    draft = small_world().draft()
    assert "non-zero" in refused(ENGINE, draft, "change_stress", amount=0, why="nothing")


def test_change_stress_acts_on_the_member() -> None:
    draft = small_world().draft()
    member = hired(draft.payload, MIRA)
    facts = change(ENGINE, draft, "change_stress", amount=1, why="a close call", actor_id=MIRA)
    assert member.dice().stress.current == 1
    assert any(fact.kind == "counter_changed" for fact in facts)


def test_use_med_kit_acts_on_the_member() -> None:
    draft = small_world().draft()
    member = hired(draft.payload, MIRA)
    member.dice().med_kit = True
    member.dice().stress.current = 3
    facts = change(ENGINE, draft, "use_med_kit", actor_id=MIRA)
    assert not member.dice().med_kit
    assert member.dice().stress.current == 1
    assert any(fact.kind == "med_kit_used" for fact in facts)


def test_drop_item_acts_on_the_member() -> None:
    draft = small_world().draft()
    member = hired(draft.payload, MIRA)
    member.dice().items[EntityId("rope")] = Item(name="Rope", die=6)
    _ = change(ENGINE, draft, "drop_item", item_id="rope", actor_id=MIRA)
    assert EntityId("rope") not in member.dice().items


def test_loot_1_or_2_leaves_a_note_and_no_pending() -> None:
    draft = small_world().draft()
    facts = ENGINE.loot_check(draft, LootCheck(item="Rope"), Random(2))
    assert draft.pending is None
    assert any("nothing is found" in note for note in draft.notes)
    assert any(fact.kind == "loot_checked" for fact in facts)


def test_loot_on_an_item_with_room_offers_take() -> None:
    draft = small_world().draft()
    _ = ENGINE.loot_check(draft, LootCheck(item="Crowbar"), Random(0))
    assert draft.pending is not None
    assert [option.id for option in draft.pending.options] == ["take"]


def test_loot_on_an_item_with_a_full_backpack_offers_swaps() -> None:
    draft = small_world().draft()
    sheet = draft.payload.player.dice()
    sheet.items[EntityId("rope")] = Item(name="Rope", die=6)
    sheet.items[EntityId("torch")] = Item(name="Torch", die=6)
    assert len(sheet.items) == 3
    _ = ENGINE.loot_check(draft, LootCheck(item="Crowbar"), Random(0))
    assert draft.pending is not None
    assert {option.id for option in draft.pending.options} == {f"swap-{key}" for key in sheet.items}
    _ = ENGINE.loot_check(
        draft, LootCheck(item="Crowbar", granted=8, choice="swap-rope"), Random(0)
    )
    assert "rope" not in sheet.items and sheet.items[EntityId("crowbar")].die == 8


def test_loot_at_d10_or_better_also_offers_a_med_kit() -> None:
    draft = small_world().draft()
    _ = ENGINE.loot_check(draft, LootCheck(item="Shotgun"), Random(17))
    assert draft.pending is not None
    ids = [option.id for option in draft.pending.options]
    assert ids == ["take", "med-kit"]


def test_loot_replay_applies_the_chosen_option() -> None:
    draft = small_world().draft()
    sheet = draft.payload.player.dice()
    taken = LootCheck(item="Machete", granted=8, choice="take")
    facts = ENGINE.loot_check(draft, taken, Random(0))
    assert sheet.items[EntityId("machete")] == Item(name="Machete", die=8)
    assert any(fact.card == "Took Machete (d8)" for fact in facts)


def test_luck_facts_are_untold() -> None:
    draft = small_world().draft()
    dice_fact, luck_fact = ENGINE.test_luck(
        draft, LuckTest(question="Is anyone home?", die=6), Random(0)
    )
    assert not dice_fact.told
    assert not luck_fact.told
    assert luck_fact.card == ""


def test_leave_and_enter_on_the_player_are_refused() -> None:
    draft = small_world().draft()
    assert "in every scene" in refused(ENGINE, draft, "leave", entity_id=PLAYER_ID)
    assert "in every scene" in refused(ENGINE, draft, "enter", entity_id=PLAYER_ID)


def test_kill_on_the_player_ends_the_game() -> None:
    draft = small_world().draft()
    facts = change(ENGINE, draft, "kill", entity_id=PLAYER_ID)
    assert not draft.payload.player.alive
    assert ENGINE.over(draft) == "You died."
    assert any(fact.card == "You are dead" for fact in facts)


def test_drop_item_removes_the_key() -> None:
    draft = small_world().draft()
    _ = change(ENGINE, draft, "drop_item", item_id=WRENCH)
    assert WRENCH not in draft.payload.player.dice().items


def test_next_scene_with_pursuit_requests_the_crossing() -> None:
    draft = small_world()
    facts = ENGINE.next_scene(draft, NextScene(pursuit="the control deck"), Random(0))
    assert draft.generation is not None and draft.generation.brief == "the control deck"
    assert SCENE_LEFT in facts
