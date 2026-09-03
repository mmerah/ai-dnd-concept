from random import Random

import pytest
from core_test_support import change, refused, the_campaign
from twentyfourxx_test_support import KESTREL, LOCKPICKS, hub_world, small_world

from aidm.core.entities import EntityId
from aidm.engines.base import PLAYER_ID
from aidm.engines.hub import JOB_DONE
from aidm.engines.scenes.tools import NextScene
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.engines.twentyfourxx.tools import AfterJob, Attempt, Defend
from aidm.engines.twentyfourxx.tools import TestLuck as LuckTest
from aidm.engines.twentyfourxx.world import STARTING_CREDITS

ENGINE = TwentyfourxxEngine()


def test_attempt_bands_disaster_setback_success() -> None:
    draft = small_world().draft()
    facts = ENGINE.attempt(draft, Attempt(what="Slip past", skill="Stealth"), Random(2))
    assert facts[1].trace.endswith("-> disaster")

    draft = small_world().draft()
    facts = ENGINE.attempt(draft, Attempt(what="Slip past", skill="Stealth"), Random(1))
    assert facts[1].trace.endswith("-> setback")

    draft = small_world().draft()
    facts = ENGINE.attempt(draft, Attempt(what="Slip past", skill="Stealth"), Random(0))
    assert facts[1].trace.endswith("-> success")


def test_attempt_unskilled_rolls_the_plain_d6() -> None:
    draft = small_world().draft()
    facts = ENGINE.attempt(draft, Attempt(what="Guess"), Random(0))
    assert facts[1].dice[0].faces == (6,)
    assert "unskilled" in facts[1].trace


def test_attempt_pack_label_not_on_sheet_rolls_d6() -> None:
    draft = small_world().draft()
    facts = ENGINE.attempt(draft, Attempt(what="Scale the wall", skill="Climbing"), Random(0))
    assert facts[1].dice[0].faces == (6,)
    assert "Climbing" in facts[1].trace


def test_attempt_unknown_skill_refused_with_both_lists() -> None:
    draft = small_world().draft()
    with pytest.raises(ValueError) as raised:
        _ = ENGINE.attempt(draft, Attempt(what="Try", skill="Nonexistent"), Random(0))
    assert "Stealth" in str(raised.value)
    assert "Climbing" in str(raised.value)


def test_attempt_hindered_rolls_d4() -> None:
    draft = small_world().draft()
    facts = ENGINE.attempt(
        draft,
        Attempt(what="Slip past", skill="Stealth", hindered="a jammed door"),
        Random(0),
    )
    assert facts[1].dice[0].faces == (4,)


def test_attempt_helped_adds_the_d6_and_keeps_highest() -> None:
    draft = small_world().draft()
    facts = ENGINE.attempt(
        draft, Attempt(what="Slip past", skill="Stealth", helped="Kestrel covers"), Random(0)
    )
    assert facts[1].dice[0].faces == (10, 6)


def test_attempt_helped_and_hindered_together_roll_4_and_6() -> None:
    draft = small_world().draft()
    facts = ENGINE.attempt(
        draft,
        Attempt(
            what="Slip past", skill="Stealth", hindered="a jammed door", helped="Kestrel covers"
        ),
        Random(0),
    )
    assert facts[1].dice[0].faces == (4, 6)


def test_risking_death_kills_on_disaster_and_maims_on_setback_not_doubled() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.attempt(
        draft, Attempt(what="Sneak past", skill="Stealth", risking_death=True), Random(1)
    )
    assert player.alive
    assert player.hindrances == ["Maimed"]
    assert any(fact.card == "Maimed" for fact in facts)

    _ = ENGINE.attempt(
        draft, Attempt(what="Sneak past", skill="Stealth", risking_death=True), Random(1)
    )
    assert player.hindrances == ["Maimed"]

    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.attempt(
        draft, Attempt(what="Sneak past", skill="Stealth", risking_death=True), Random(2)
    )
    assert not player.alive
    assert any(fact.card == "You are dead" for fact in facts)


def test_luck_facts_are_untold() -> None:
    draft = small_world().draft()
    dice_fact, luck_fact = ENGINE.test_luck(draft, LuckTest(question="Is anyone home?"), Random(0))
    assert not dice_fact.told
    assert not luck_fact.told
    assert luck_fact.card == ""


def test_defend_breaks_the_item_and_adds_the_hindrance_refused_when_broken() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.defend(draft, Defend(item_id=LOCKPICKS, hindrance="fingers cut"), Random(0))
    assert player.items[LOCKPICKS].broken_times == 1
    assert player.items[LOCKPICKS].broken
    assert "fingers cut" in player.hindrances
    assert any(fact.card == "Lockpick set breaks — fingers cut" for fact in facts)

    with pytest.raises(ValueError, match="already broken"):
        _ = ENGINE.defend(
            draft, Defend(item_id=LOCKPICKS, hindrance="fingers cut again"), Random(0)
        )


def test_gain_item_spends_and_refuses_short_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    assert player.credits == STARTING_CREDITS
    _ = change(ENGINE, draft, "gain_item", name="Rope", cost=1)
    assert player.credits == STARTING_CREDITS - 1
    assert player.items[EntityId("rope")].name == "Rope"

    assert "only" in refused(ENGINE, draft, "gain_item", name="Grenade", cost=99)


def test_spend_refuses_short_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = change(ENGINE, draft, "spend", amount=1, why="a bribe")
    assert player.credits == STARTING_CREDITS - 1
    assert "only" in refused(ENGINE, draft, "spend", amount=99, why="a bigger bribe")


def test_repair_item_zeroes_broken_times_and_refuses_an_unbroken_item() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    assert "not broken" in refused(ENGINE, draft, "repair_item", item_id=LOCKPICKS)

    player.items[LOCKPICKS].broken_times = 1
    _ = change(ENGINE, draft, "repair_item", item_id=LOCKPICKS)
    assert player.items[LOCKPICKS].broken_times == 0


def test_change_hindrances_gains_and_loses_refuses_duplicate_and_absent() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = change(ENGINE, draft, "change_hindrances", gained=["Bleeding"])
    assert player.hindrances == ["Bleeding"]

    assert "already" in refused(ENGINE, draft, "change_hindrances", gained=["Bleeding"])
    assert "not among" in refused(ENGINE, draft, "change_hindrances", lost=["Scared"])

    _ = change(ENGINE, draft, "change_hindrances", gained=["Scared"], lost=["Bleeding"])
    assert player.hindrances == ["Scared"]


def test_after_job_raises_a_skill_enters_a_new_one_refuses_at_d12_adds_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    before_credits = player.credits

    facts = ENGINE.after_job(draft, AfterJob(skill="Stealth"), Random(0))
    assert player.skills["Stealth"] == 12
    assert player.credits == before_credits + 4
    assert any(fact.card == "Skill up: Stealth d12" for fact in facts)

    _ = ENGINE.after_job(draft, AfterJob(skill="Climbing"), Random(1))
    assert player.skills["Climbing"] == 8

    with pytest.raises(ValueError, match="d12"):
        _ = ENGINE.after_job(draft, AfterJob(skill="Stealth"), Random(0))


def test_kill_on_the_player_flips_player_over() -> None:
    draft = small_world().draft()
    facts = change(ENGINE, draft, "kill", entity_id=PLAYER_ID)
    assert not draft.payload.player.alive
    assert ENGINE.over(draft) == "You died."
    assert any(fact.card == "You are dead" for fact in facts)


def test_next_scene_settles_and_refuses_a_second_call() -> None:
    draft = small_world().draft()
    facts = ENGINE.next_scene(draft, NextScene(), Random(0))
    assert draft.payload.run.left is not None
    assert facts[0].kind == "scene_settled"
    with pytest.raises(ValueError, match="already settled"):
        _ = ENGINE.next_scene(draft, NextScene(), Random(0))


def test_next_scene_with_job_done_settles_the_job_and_is_refused_at_the_hub() -> None:
    draft = hub_world()
    world = draft.payload
    facts = ENGINE.next_scene(draft, NextScene(job_done=True), Random(0))
    assert world.run.left is not None
    assert the_campaign(world.campaign).jobs[-1].finished
    assert JOB_DONE in facts

    at_hub = hub_world()
    at_hub.payload.runs = [at_hub.payload.runs[0]]
    with pytest.raises(ValueError, match="no job is open here"):
        _ = ENGINE.next_scene(at_hub, NextScene(job_done=True), Random(0))


def test_leave_takes_a_cast_member_out() -> None:
    draft = small_world().draft()
    assert "leaves" in change(ENGINE, draft, "leave", entity_id=KESTREL)[0].trace
