from random import Random

import pytest
from support.breathless import WRENCH, hub_world, small_world
from support.table import change, refused, the_campaign

from aidm.core.entities import EntityId, Refusal
from aidm.core.tools import NoArgs
from aidm.engines.base import PLAYER_ID
from aidm.engines.breathless.engine import BreathlessEngine
from aidm.engines.breathless.tools import ChangeStress, Check, LootCheck
from aidm.engines.breathless.tools import TestLuck as LuckTest
from aidm.engines.breathless.world import Item, stepped
from aidm.engines.hub import JOB_DONE
from aidm.engines.scenes.tools import NextScene
from aidm.engines.scenes.world import SCENE_LEFT

ENGINE = BreathlessEngine()


def test_check_on_a_skill_wears_it() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.check(draft, Check(what="Force the door", skill="bash"), Random(0))
    assert player.worn["bash"] == stepped(6)
    assert any(fact.kind == "checked" for fact in facts)


def test_check_at_d4_stays_d4() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = ENGINE.check(draft, Check(what="Spot a way through", skill="dash"), Random(1))
    assert player.worn["dash"] == 4


def test_an_item_reduced_to_d4_is_gone() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.items[WRENCH].die = 6
    facts = ENGINE.check(draft, Check(what="Swing the axe", item_id=WRENCH), Random(0))
    assert WRENCH not in player.items
    assert any(fact.kind == "item_gone" for fact in facts)


def test_stunt_refused_twice() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = ENGINE.check(draft, Check(what="Leap the gap", stunt=True), Random(0))
    assert player.stunted
    with pytest.raises(Refusal, match="catches their breath"):
        _ = ENGINE.check(draft, Check(what="Leap again", stunt=True), Random(0))


def test_check_needs_exactly_one_of_skill_item_or_stunt() -> None:
    with pytest.raises(ValueError, match="roll one thing"):
        Check(what="Do something")
    with pytest.raises(ValueError, match="roll one thing"):
        Check(what="Do something", skill="bash", stunt=True)


def test_vulnerable_fail_leaves_a_note() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.stress.current = 4
    _ = ENGINE.check(draft, Check(what="Force the door", skill="bash", dangerous=True), Random(2))
    assert any("vulnerable" in note for note in draft.notes)


def test_catch_breath_resets_worn_loot_and_stunt_but_keeps_stress_and_item_dice() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.worn["bash"] = 4
    player.loot = 6
    player.stunted = True
    player.stress.current = 2
    player.items[WRENCH].die = 6

    facts = ENGINE.catch_breath(draft, NoArgs(), Random(0))

    assert player.worn == player.skills
    assert player.loot == 12
    assert not player.stunted
    assert player.stress.current == 2
    assert player.items[WRENCH].die == 6
    assert any("The SRD's table suggests" in note for note in draft.notes)
    assert {fact.kind for fact in facts} == {"dice_rolled", "breath_caught"}
    assert next(f for f in facts if f.kind == "breath_caught").card == (
        "Caught breath — skills and loot die restored"
    )


def test_use_med_kit_refused_without_a_kit() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="holds no med kit"):
        _ = ENGINE.use_med_kit(draft, NoArgs(), Random(0))


def test_use_med_kit_clears_two_stress() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.med_kit = True
    player.stress.current = 3
    facts = ENGINE.use_med_kit(draft, NoArgs(), Random(0))
    assert not player.med_kit
    assert player.stress.current == 1
    assert any(fact.kind == "med_kit_used" for fact in facts)


def test_change_stress_refuses_a_zero_amount() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="non-zero"):
        _ = ENGINE.change_stress(draft, ChangeStress(amount=0, why="nothing"), Random(0))


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
    player = draft.payload.player
    player.items[EntityId("rope")] = Item(name="Rope", die=6)
    player.items[EntityId("torch")] = Item(name="Torch", die=6)
    assert len(player.items) == 3
    _ = ENGINE.loot_check(draft, LootCheck(item="Crowbar"), Random(0))
    assert draft.pending is not None
    assert {option.id for option in draft.pending.options} == {
        f"swap-{key}" for key in player.items
    }
    _ = ENGINE.loot_check(
        draft, LootCheck(item="Crowbar", granted=8, choice="swap-rope"), Random(0)
    )
    assert "rope" not in player.items and player.items[EntityId("crowbar")].die == 8


def test_loot_at_d10_or_better_also_offers_a_med_kit() -> None:
    draft = small_world().draft()
    _ = ENGINE.loot_check(draft, LootCheck(item="Shotgun"), Random(17))
    assert draft.pending is not None
    ids = [option.id for option in draft.pending.options]
    assert ids == ["take", "med-kit"]


def test_loot_replay_applies_the_chosen_option() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    taken = LootCheck(item="Machete", granted=8, choice="take")
    facts = ENGINE.loot_check(draft, taken, Random(0))
    key = EntityId("machete")
    assert player.items[key] == Item(name="Machete", die=8)
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
    assert WRENCH not in draft.payload.player.items


def test_next_scene_with_job_done_settles_the_job_and_is_refused_at_the_hub() -> None:
    draft = hub_world()
    world = draft.payload
    facts = ENGINE.next_scene(draft, NextScene(job_done=True), Random(0))
    assert world.run.left is not None
    assert the_campaign(world.campaign).jobs[-1].finished
    assert JOB_DONE in facts

    at_hub = hub_world()
    at_hub.payload.runs = [at_hub.payload.runs[0]]
    with pytest.raises(Refusal, match="no job is open here"):
        _ = ENGINE.next_scene(at_hub, NextScene(job_done=True), Random(0))


def test_next_scene_with_pursuit_settles_the_run_and_leaves_a_go_on_row() -> None:
    draft = hub_world()
    world = draft.payload
    facts = ENGINE.next_scene(draft, NextScene(pursuit="the control deck"), Random(0))
    assert world.run.left == "the control deck"
    assert SCENE_LEFT in facts
    assert any(
        row.label == "Go on" and row.intent == "the control deck" for row in world.scene_rows()
    )
