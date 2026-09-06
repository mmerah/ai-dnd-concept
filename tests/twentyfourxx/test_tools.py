import asyncio
from random import Random

import pytest
from pydantic import BaseModel
from support.table import change, refused
from support.twentyfourxx import KESTREL, LOCKPICKS, SABLE, hired, small_world

from aidm.core.entities import EntityId, Refusal
from aidm.core.model import Check, Generation
from aidm.engines.base import HIRE, PLAYER_ID, SIGNED_ON, SRD_PACK, Hire
from aidm.engines.scenes.tools import NextScene
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine
from aidm.engines.twentyfourxx.tools import Job, Raise, Roll
from aidm.engines.twentyfourxx.tools import TestLuck as LuckTest
from aidm.engines.twentyfourxx.world import STARTING_CREDITS, UPGRADE_COST

ENGINE = TwentyfourxxEngine()


def test_attempt_bands_disaster_setback_success() -> None:
    draft = small_world().draft()
    facts = ENGINE.roll(draft, Roll(what="Slip past", skill="Stealth"), Random(2))
    assert facts[1].trace.endswith("→ disaster")

    draft = small_world().draft()
    facts = ENGINE.roll(draft, Roll(what="Slip past", skill="Stealth"), Random(1))
    assert facts[1].trace.endswith("→ setback")

    draft = small_world().draft()
    facts = ENGINE.roll(draft, Roll(what="Slip past", skill="Stealth"), Random(0))
    assert facts[1].trace.endswith("→ success")


def test_attempt_unskilled_rolls_the_plain_d6() -> None:
    draft = small_world().draft()
    facts = ENGINE.roll(draft, Roll(what="Guess"), Random(0))
    assert facts[1].dice[0].faces == (6,)
    assert "Unskilled" in facts[1].trace


def test_attempt_pack_label_not_on_sheet_rolls_d6() -> None:
    draft = small_world().draft()
    facts = ENGINE.roll(draft, Roll(what="Scale the wall", skill="Climbing"), Random(0))
    assert facts[1].dice[0].faces == (6,)
    assert "Climbing" in facts[1].trace


def test_attempt_unknown_skill_refused_with_both_lists() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal) as raised:
        _ = ENGINE.roll(draft, Roll(what="Try", skill="Nonexistent"), Random(0))
    assert "Stealth" in str(raised.value)
    assert "Climbing" in str(raised.value)


def test_attempt_hindered_rolls_d4() -> None:
    draft = small_world().draft()
    facts = ENGINE.roll(
        draft,
        Roll(what="Slip past", skill="Stealth", hindered="a jammed door"),
        Random(0),
    )
    assert facts[1].dice[0].faces == (4,)


def test_attempt_helped_adds_the_d6_and_keeps_highest() -> None:
    draft = small_world().draft()
    facts = ENGINE.roll(
        draft, Roll(what="Slip past", skill="Stealth", helped="Kestrel covers"), Random(0)
    )
    assert facts[1].dice[0].faces == (10, 6)


def test_attempt_helped_and_hindered_together_roll_4_and_6() -> None:
    draft = small_world().draft()
    facts = ENGINE.roll(
        draft,
        Roll(what="Slip past", skill="Stealth", hindered="a jammed door", helped="Kestrel covers"),
        Random(0),
    )
    assert facts[1].dice[0].faces == (4, 6)


def test_attempt_helped_by_rolls_two_dice_and_keeps_highest() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 8}).draft()
    facts = ENGINE.roll(
        draft, Roll(what="Slip past", skill="Stealth", helped_by=KESTREL), Random(0)
    )
    assert facts[1].dice[0].faces == (10, 8)
    assert facts[1].dice[0].label == "d10+d8"
    assert "helped by Kestrel (d8)" in facts[1].trace


def test_attempt_actor_id_acts_on_the_member_and_risking_death_kills_them() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 10}).draft()
    facts = ENGINE.roll(
        draft,
        Roll(what="Slip past", actor_id=KESTREL, skill="Stealth", risking_death=True),
        Random(2),
    )
    member = draft.payload.cast[KESTREL]
    assert not member.alive
    assert draft.payload.player.alive
    assert any(fact.card == f"{member.name} is dead" for fact in facts)
    attempted = next(fact for fact in facts if fact.kind == "attempted")
    assert attempted.trace.startswith("Slip past — Kestrel: ")


def test_risking_death_kills_on_disaster_and_maims_on_setback_not_doubled() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.roll(
        draft, Roll(what="Sneak past", skill="Stealth", risking_death=True), Random(1)
    )
    assert player.alive
    assert player.dice().hindrances == ["Maimed"]
    assert any(fact.card == "Maimed" for fact in facts)

    _ = ENGINE.roll(draft, Roll(what="Sneak past", skill="Stealth", risking_death=True), Random(1))
    assert player.dice().hindrances == ["Maimed"]

    draft = small_world().draft()
    player = draft.payload.player
    facts = ENGINE.roll(
        draft, Roll(what="Sneak past", skill="Stealth", risking_death=True), Random(2)
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
    facts = change(ENGINE, draft, "defend", item_id=LOCKPICKS, hindrance="fingers cut")
    assert player.dice().items[LOCKPICKS].broken_times == 1
    assert player.dice().items[LOCKPICKS].broken
    assert "fingers cut" in player.dice().hindrances
    assert any(fact.card == "Lockpick set breaks — fingers cut" for fact in facts)

    assert "already broken" in refused(
        ENGINE, draft, "defend", item_id=LOCKPICKS, hindrance="fingers cut again"
    )


def test_defend_refuses_an_empty_hindrance_on_a_carried_item() -> None:
    draft = small_world().draft()
    assert "name the hindrance" in refused(ENGINE, draft, "defend", item_id=LOCKPICKS)


def test_defend_hull_armor_breaks_harmlessly_and_refuses_a_hindrance() -> None:
    draft = small_world().draft()
    facts = change(ENGINE, draft, "defend", item_id="hull-armor")
    assert draft.payload.ship[EntityId("hull-armor")].broken
    assert draft.payload.player.dice().hindrances == []
    assert any(fact.card == "Hull armor breaks" for fact in facts)

    draft = small_world().draft()
    assert "leave `hindrance` empty" in refused(
        ENGINE, draft, "defend", item_id="hull-armor", hindrance="hull breached"
    )


def test_gain_item_spends_and_refuses_short_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    assert player.dice().credits == STARTING_CREDITS
    _ = change(ENGINE, draft, "gain_item", name="Rope", cost=1)
    assert player.dice().credits == STARTING_CREDITS - 1
    assert player.dice().items[EntityId("rope")].name == "Rope"

    assert "only" in refused(ENGINE, draft, "gain_item", name="Grenade", cost=99)


def test_spend_refuses_short_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = change(ENGINE, draft, "spend", amount=1, why="a bribe")
    assert player.dice().credits == STARTING_CREDITS - 1
    assert "only" in refused(ENGINE, draft, "spend", amount=99, why="a bigger bribe")


def test_change_world_spend_with_actor_id_pays_from_the_member_credits() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    member = draft.payload.cast[KESTREL]
    before = member.dice().credits
    _ = change(ENGINE, draft, "spend", amount=1, why="ammo", actor_id=KESTREL)
    assert member.dice().credits == before - 1
    assert draft.payload.player.dice().credits == STARTING_CREDITS


def test_repair_item_zeroes_broken_times_and_refuses_an_unbroken_item() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    assert "not broken" in refused(ENGINE, draft, "repair_item", item_id=LOCKPICKS)

    player.dice().items[LOCKPICKS].broken_times = 1
    _ = change(ENGINE, draft, "repair_item", item_id=LOCKPICKS)
    assert player.dice().items[LOCKPICKS].broken_times == 0


def test_change_hindrances_gains_and_loses_refuses_duplicate_and_absent() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = change(ENGINE, draft, "change_hindrances", gained=["Bleeding"])
    assert player.dice().hindrances == ["Bleeding"]

    assert "already" in refused(ENGINE, draft, "change_hindrances", gained=["Bleeding"])
    assert "not among" in refused(ENGINE, draft, "change_hindrances", lost=["Scared"])

    _ = change(ENGINE, draft, "change_hindrances", gained=["Scared"], lost=["Bleeding"])
    assert player.dice().hindrances == ["Scared"]


def test_finish_job_raises_a_skill_enters_a_new_one_refuses_at_d12_adds_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    before_credits = player.dice().credits

    draft.payload.job = "Escort the crate to dock nine"
    facts = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))
    assert player.dice().skills["Stealth"] == 12
    assert player.dice().credits == before_credits + 4
    assert any(fact.card == "Job done: Stealth d12" for fact in facts)
    assert draft.payload.job == ""

    draft.payload.job = "Shadow the courier"
    _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Climbing"),)), Random(1))
    assert player.dice().skills["Climbing"] == 8

    draft.payload.job = "One skill too far"
    with pytest.raises(Refusal, match="d12"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))


def test_finish_job_refuses_raises_missing_a_hired_member() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    draft.payload.job = "Escort the crate"
    with pytest.raises(Refusal, match="the player and every living hired member"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))


def test_finish_job_refuses_raises_that_name_the_player_twice() -> None:
    draft = small_world().draft()
    draft.payload.job = "Escort the crate"
    with pytest.raises(Refusal, match="repeated the player"):
        _ = ENGINE.job(
            draft,
            Job(verb="finish", raises=(Raise(skill="Stealth"), Raise(skill="Climbing"))),
            Random(0),
        )


def test_finish_job_raises_the_whole_crew_and_pays_each_a_d6() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    player = draft.payload.player
    member = draft.payload.cast[KESTREL]
    before_member_credits = member.dice().credits
    draft.payload.job = "Escort the crate"

    facts = ENGINE.job(
        draft,
        Job(
            verb="finish",
            raises=(Raise(skill="Stealth"), Raise(actor_id=KESTREL, skill="Shooting")),
        ),
        Random(0),
    )

    assert player.dice().skills["Stealth"] == 12
    assert member.dice().skills["Shooting"] == 10
    assert member.dice().credits > before_member_credits
    assert any(fact.card == "Job done: Shooting d10" for fact in facts)


def test_android_case_is_an_item_on_creation_and_defend_breaks_it() -> None:
    picks = {
        "pack": "srd",
        "specialty": "tech",
        "origin": "android",
        "increase-1": "climbing",
        "body": "case",
    }
    character = ENGINE.create_character("Unit-9", "A tireless drone", picks)
    android = character.payload
    sheet = android.dice()
    case_id = next(item_id for item_id, item in sheet.items.items() if item.name == "Case")

    draft = small_world().draft()
    draft.payload.player = android

    facts = change(ENGINE, draft, "defend", item_id=case_id, hindrance="dented")
    assert draft.payload.player.dice().items[case_id].broken
    assert any(fact.card == "Case breaks — dented" for fact in facts)


def test_take_job_opens_a_job_and_refuses_a_second_while_open() -> None:
    draft = small_world().draft()
    facts = ENGINE.job(draft, Job(verb="take", terms="Move the crates by dawn"), Random(0))
    assert draft.payload.job == "Move the crates by dawn"
    assert any(fact.card == "Job taken\nMove the crates by dawn" for fact in facts)

    with pytest.raises(Refusal, match="a job is open"):
        _ = ENGINE.job(draft, Job(verb="take", terms="A second job"), Random(0))


def test_find_job_reads_the_three_bands_by_seed() -> None:
    draft = small_world().draft()
    facts = ENGINE.job(draft, Job(verb="find", where="Docks"), Random(1))
    assert facts[1].trace.endswith("nothing; the player owes somebody to get in on a job")

    draft = small_world().draft()
    facts = ENGINE.job(draft, Job(verb="find", where="Docks"), Random(0))
    assert facts[1].trace.endswith("a job, but something seems off")

    draft = small_world().draft()
    facts = ENGINE.job(draft, Job(verb="find", where="Docks"), Random(5))
    assert facts[1].trace.endswith("a choice between two jobs")


def test_find_job_refused_while_a_job_is_open() -> None:
    draft = small_world().draft()
    draft.payload.job = "Move the crates by dawn"
    with pytest.raises(Refusal, match="a job is open"):
        _ = ENGINE.job(draft, Job(verb="find", where="Docks"), Random(0))


def test_finish_job_refuses_without_a_job_open() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="no job is open"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))


def test_finish_job_pays_once_and_refuses_a_second_call() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    before_credits = player.dice().credits

    draft.payload.job = "Deliver the package"
    _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))
    assert player.dice().credits == before_credits + 4
    assert draft.payload.job == ""

    with pytest.raises(Refusal, match="no job is open"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))
    assert player.dice().credits == before_credits + 4


def test_job_validator_refuses_fields_that_do_not_match_the_verb() -> None:
    with pytest.raises(ValueError, match="find takes where only"):
        _ = Job(verb="find")
    with pytest.raises(ValueError, match="find takes where only"):
        _ = Job(verb="find", where="Docks", terms="extra")
    with pytest.raises(ValueError, match="take takes terms only"):
        _ = Job(verb="take")
    with pytest.raises(ValueError, match="take takes terms only"):
        _ = Job(verb="take", terms="agreed", where="Docks")
    with pytest.raises(ValueError, match="finish takes raises only"):
        _ = Job(verb="finish")
    with pytest.raises(ValueError, match="finish takes raises only"):
        _ = Job(verb="finish", raises=(Raise(skill="Stealth"),), terms="agreed")


def test_kill_on_the_player_flips_player_over() -> None:
    draft = small_world().draft()
    facts = change(ENGINE, draft, "kill", entity_id=PLAYER_ID)
    assert not draft.payload.player.alive
    assert ENGINE.over(draft) == "You died."
    assert any(fact.card == "You are dead" for fact in facts)


def test_risking_death_disaster_with_hired_member_sets_succession_and_over_stays_none() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    facts = ENGINE.roll(
        draft, Roll(what="Slip past", skill="Stealth", risking_death=True), Random(2)
    )
    assert not draft.payload.player.alive
    assert draft.pending is not None
    assert draft.pending.kind == "succession"
    assert [option.id for option in draft.pending.options] == [KESTREL]
    assert ENGINE.over(draft) is None
    assert any(fact.card == "You are dead" for fact in facts)


def test_risking_death_disaster_with_none_hired_ends_the_game() -> None:
    draft = small_world().draft()
    _ = ENGINE.roll(draft, Roll(what="Slip past", skill="Stealth", risking_death=True), Random(2))
    assert not draft.payload.player.alive
    assert draft.pending is None
    assert ENGINE.over(draft) == "You died."


def test_answering_the_succession_decision_makes_the_member_the_player() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    _ = ENGINE.roll(draft, Roll(what="Slip past", skill="Stealth", risking_death=True), Random(2))
    assert draft.pending is not None
    option = draft.pending.options[0]
    facts = ENGINE.answer(draft, option, Random(0))
    assert draft.payload.player.id == KESTREL
    assert any(fact.card == "Kestrel leads now" for fact in facts)


def test_ship_upgrade_pays_credits_once_and_refuses_a_second() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.dice().credits = UPGRADE_COST * 2
    before = player.dice().credits
    facts = change(ENGINE, draft, "ship_upgrade", function_id="hull-armor")
    assert player.dice().credits == before - UPGRADE_COST
    assert draft.payload.ship[EntityId("hull-armor")].upgraded
    assert any(fact.card == "Hull armor upgraded — ₡10" for fact in facts)

    assert "already" in refused(ENGINE, draft, "ship_upgrade", function_id="hull-armor")


def test_defend_and_repair_item_on_the_ships_hull_armor() -> None:
    draft = small_world().draft()
    _ = change(ENGINE, draft, "defend", item_id="hull-armor")
    assert draft.payload.ship[EntityId("hull-armor")].broken

    _ = change(ENGINE, draft, "repair_item", item_id="hull-armor")
    assert not draft.payload.ship[EntityId("hull-armor")].broken


def test_next_scene_offers_the_way_on_and_refuses_a_second_offer() -> None:
    draft = small_world().draft()
    facts = ENGINE.next_scene(draft, NextScene(), Random(0))
    assert draft.payload.run.offered
    assert facts[0].kind == "way_offered"
    with pytest.raises(Refusal, match="already offers"):
        _ = ENGINE.next_scene(draft, NextScene(), Random(0))


def test_leave_takes_a_cast_member_out() -> None:
    draft = small_world().draft()
    assert "leaves" in change(ENGINE, draft, "leave", entity_id=KESTREL)[0].trace


def test_hire_sets_generation_and_ends_the_turn() -> None:
    draft = small_world().draft()
    facts = ENGINE.hire(draft, Hire(entity_id=KESTREL, terms="Watch our backs"), Random(0))
    assert draft.generation == Generation(operation=HIRE, brief="Watch our backs", target=KESTREL)
    assert any(fact.kind == "hire_asked" for fact in facts)


def test_hire_refuses_a_sheeted_member() -> None:
    draft = small_world().draft()
    with pytest.raises(Refusal, match="already carries a sheet"):
        _ = ENGINE.hire(draft, Hire(entity_id=PLAYER_ID, terms="terms"), Random(0))


def test_validate_refuses_a_hire_with_no_target() -> None:
    draft = small_world().draft()
    draft.packs = (SRD_PACK,)
    draft.generation = Generation(operation=HIRE, brief="terms")
    with pytest.raises(Refusal, match="a hire names who signs on"):
        ENGINE.validate(draft)


def test_validate_refuses_a_hire_whose_target_is_not_here_or_already_sheeted() -> None:
    draft = small_world().draft()
    draft.packs = (SRD_PACK,)
    draft.generation = Generation(operation=HIRE, brief="terms", target=SABLE)
    with pytest.raises(Refusal, match="is not here with the player"):
        ENGINE.validate(draft)

    draft = small_world().draft()
    draft.packs = (SRD_PACK,)
    draft.generation = Generation(operation=HIRE, brief="terms", target=PLAYER_ID)
    with pytest.raises(Refusal, match="already carries a sheet"):
        ENGINE.validate(draft)


async def _stub_worldsmith[M: BaseModel](prompt: str, model: type[M], refusal: Check[M]) -> M:
    del prompt, refusal
    return model.model_validate(
        {"specialty": "Muscle", "skills": {"Intimidation": 8}, "items": ["Crowbar"]}
    )


def test_advance_on_a_hire_installs_the_sheet_and_joins_the_party() -> None:
    draft = small_world().draft()
    draft.packs = (SRD_PACK,)
    generation = Generation(operation=HIRE, brief="Watch our backs", target=KESTREL)
    facts, told = asyncio.run(ENGINE.advance(draft, generation, _stub_worldsmith))
    member = draft.payload.cast[KESTREL]
    assert member.dice().credits == 0
    assert [item.name for item in member.dice().items.values()] == ["Crowbar"]
    assert KESTREL in draft.payload.party
    assert told == SIGNED_ON.format(name=member.name)
    assert any(fact.kind == "hired" for fact in facts)
