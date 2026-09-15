from random import Random

import pytest
from support.table import change, refused
from support.twentyfourxx import ENGINE, KESTREL, LOCKPICKS, SABLE, hired, small_world

from aidm.core.entities import Refusal
from aidm.core.facts import Fact
from aidm.engines.base import PLAYER_ID, AskWorld
from aidm.engines.scenes.tools import NextScene
from aidm.engines.twentyfourxx.engine import items_from_kits
from aidm.engines.twentyfourxx.tools import Helper, Job, Raise, Roll
from aidm.engines.twentyfourxx.world import (
    SHIP_IDS,
    STARTING_CREDITS,
    UPGRADE_COST,
    Gear,
    TwentyfourxxGame,
)
from aidm.engines.twentyfourxx.worldsmith import Kit


def _rolled(draft: TwentyfourxxGame, roll: Roll, *, seed: int = 0) -> list[Fact]:
    return ENGINE.roll(draft, roll, Random(seed))


def test_attempt_bands_disaster_setback_success() -> None:
    draft = small_world().draft()
    facts = _rolled(draft, Roll(what="Slip past", skill="Stealth"), seed=2)
    assert facts[1].trace.endswith("→ disaster")

    draft = small_world().draft()
    facts = _rolled(draft, Roll(what="Slip past", skill="Stealth"), seed=1)
    assert facts[1].trace.endswith("→ setback")

    draft = small_world().draft()
    facts = _rolled(draft, Roll(what="Slip past", skill="Stealth"))
    assert facts[1].trace.endswith("→ success")


def test_attempt_unskilled_rolls_the_plain_d6(draft: TwentyfourxxGame) -> None:
    facts = _rolled(draft, Roll(what="Guess"))
    assert facts[1].dice[0].faces == (6,)
    assert "Unskilled" in facts[1].trace


def test_attempt_pack_label_not_on_sheet_rolls_d6(draft: TwentyfourxxGame) -> None:
    facts = _rolled(draft, Roll(what="Scale the wall", skill="Climbing"))
    assert facts[1].dice[0].faces == (6,)
    assert "Climbing" in facts[1].trace


def test_attempt_unknown_skill_refused_with_both_lists(draft: TwentyfourxxGame) -> None:
    with pytest.raises(Refusal) as raised:
        _ = _rolled(draft, Roll(what="Try", skill="Nonexistent"))
    assert "Stealth" in str(raised.value)
    assert "Climbing" in str(raised.value)


def test_attempt_hindered_rolls_d4(draft: TwentyfourxxGame) -> None:
    facts = _rolled(draft, Roll(what="Slip past", skill="Stealth", hindered="a jammed door"))
    assert facts[1].dice[0].faces == (4,)


def test_attempt_helped_adds_the_d6_and_keeps_highest(draft: TwentyfourxxGame) -> None:
    facts = _rolled(draft, Roll(what="Slip past", skill="Stealth", helped="Kestrel covers"))
    assert facts[1].dice[0].faces == (10, 6)


def test_attempt_helped_and_hindered_together_roll_4_and_6(draft: TwentyfourxxGame) -> None:
    facts = _rolled(
        draft,
        Roll(what="Slip past", skill="Stealth", hindered="a jammed door", helped="Kestrel covers"),
    )
    assert facts[1].dice[0].faces == (4, 6)


def test_attempt_helped_by_rolls_two_dice_and_keeps_highest(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Stealth": 8}).draft()
    facts = _rolled(
        draft, Roll(what="Slip past", skill="Stealth", helped_by=Helper(actor_id=KESTREL))
    )
    assert facts[1].dice[0].faces == (10, 8)
    assert facts[1].dice[0].label == "d10+d8"
    assert "helped by Kestrel (d8)" in facts[1].trace


def test_attempt_actor_id_acts_on_the_member_and_risk_kills_them(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Stealth": 10}).draft()
    facts = _rolled(
        draft,
        Roll(what="Slip past", actor_id=KESTREL, skill="Stealth", risk="a long fall", deadly=True),
        seed=2,
    )
    member = draft.payload.cast[KESTREL]
    assert not member.alive
    assert draft.payload.player.alive
    assert any(fact.card == f"{member.name} is dead" for fact in facts)
    assert facts[1].trace.startswith("Slip past — Kestrel: ")


def test_deadly_disaster_kills() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = _rolled(
        draft, Roll(what="Sneak past", skill="Stealth", risk="a guard's knife", deadly=True), seed=2
    )
    assert not player.alive
    assert any(fact.card == "You are dead" for fact in facts)


def test_non_deadly_disaster_leaves_the_named_risk_as_a_hindrance_instead_of_killing() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = _rolled(draft, Roll(what="Sneak past", skill="Stealth", risk="a guard's knife"), seed=2)
    assert player.alive
    assert player.require_sheet().hindrances == ["a guard's knife"]
    assert any(fact.card == "Hindered: a guard's knife" for fact in facts)


def test_deadly_setback_maims_not_doubled() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = _rolled(
        draft, Roll(what="Sneak past", skill="Stealth", risk="a guard's knife", deadly=True), seed=1
    )
    assert player.alive
    assert player.require_sheet().hindrances == ["Maimed"]
    assert any(fact.card == "Hindered: Maimed" for fact in facts)

    _ = _rolled(
        draft, Roll(what="Sneak past", skill="Stealth", risk="a guard's knife", deadly=True), seed=1
    )
    assert player.require_sheet().hindrances == ["Maimed"]


def test_non_deadly_setback_with_no_hindrance_named_lands_nothing() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = _rolled(draft, Roll(what="Sneak past", skill="Stealth", risk="a guard's knife"), seed=1)
    assert player.alive
    assert player.require_sheet().hindrances == []
    assert len(facts) == 2


def test_roll_refuses_naming_an_unmet_entity_in_a_free_text_field(draft: TwentyfourxxGame) -> None:
    assert "not met" in refused(ENGINE, draft, "roll", what="Slip past Sable", skill="Stealth")

    facts = change(ENGINE, draft, "roll", what="Slip past Kestrel", skill="Stealth")
    assert "Slip past Kestrel" in facts[1].trace


def test_roll_helped_by_refuses_naming_an_unmet_entity_but_allows_a_revealed_one() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 8}).draft()

    assert "not met" in refused(
        ENGINE,
        draft,
        "roll",
        what="Slip past",
        skill="Stealth",
        helped_by={"actor_id": KESTREL, "hindered": "Sable spots them"},
    )

    facts = change(
        ENGINE,
        draft,
        "roll",
        what="Slip past",
        skill="Stealth",
        helped_by={"actor_id": KESTREL, "hindered": "Kestrel trips"},
    )
    assert "Kestrel trips" in facts[1].trace


def test_defend_with_intact_item_spares_a_disaster_breaks_the_item_once() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = _rolled(
        draft,
        Roll(
            what="Sneak past",
            skill="Stealth",
            risk="a guard's knife",
            defend_with=LOCKPICKS,
            hindrance="cut fingers",
        ),
        seed=2,
    )
    assert player.alive
    assert player.require_sheet().items[LOCKPICKS].broken_times == 1
    assert player.require_sheet().hindrances == ["cut fingers"]
    assert draft.pending is None
    assert any(fact.card == "Lockpick set breaks — cut fingers" for fact in facts)


def test_defend_no_longer_brands_the_actor_with_the_risk_text(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    _ = _rolled(
        draft,
        Roll(
            what="Sneak past",
            skill="Stealth",
            risk="a guard's knife",
            defend_with=LOCKPICKS,
            hindrance="cut fingers",
        ),
        seed=2,
    )
    assert "a guard's knife" not in player.require_sheet().hindrances
    assert "cut fingers" in player.require_sheet().hindrances


def test_defend_with_harmless_gear_spares_a_disaster_and_adds_no_hindrance() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = _rolled(
        draft,
        Roll(what="Weather the blast", skill="Stealth", risk="shrapnel", defend_with="hull-armor"),
        seed=2,
    )
    assert player.alive
    assert draft.payload.ship["hull-armor"].broken
    assert player.require_sheet().hindrances == []
    assert any(fact.card == "Hull armor breaks" for fact in facts)


def test_defend_with_already_broken_gear_is_refused_before_any_dice_roll() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.require_sheet().items[LOCKPICKS].broken_times = 1
    before = draft.model_copy(deep=True)
    with pytest.raises(Refusal, match="already broken"):
        _ = _rolled(
            draft,
            Roll(what="Sneak past", skill="Stealth", risk="a guard's knife", defend_with=LOCKPICKS),
            seed=2,
        )
    assert draft.payload == before.payload


def test_defend_with_multi_use_armor_defends_three_times_then_refuses() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.require_sheet().items["armor"] = Gear(name="Battle armor", breaks=3, harmless=True)
    for _ in range(3):
        _ = _rolled(
            draft,
            Roll(what="Take fire", skill="Stealth", risk="a bullet", defend_with="armor"),
            seed=2,
        )
    assert player.alive
    assert player.require_sheet().items["armor"].broken
    with pytest.raises(Refusal, match="already broken"):
        _ = _rolled(
            draft,
            Roll(what="Take fire", skill="Stealth", risk="a bullet", defend_with="armor"),
            seed=2,
        )


def test_defend_with_non_harmless_multi_use_armor_takes_a_different_hindrance_each_time() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    player.require_sheet().items["armor"] = Gear(name="Battle armor", breaks=3)
    for hindrance in ("a bruised rib", "a ringing ear", "a torn sleeve"):
        _ = _rolled(
            draft,
            Roll(
                what="Take fire",
                skill="Stealth",
                risk="a bullet",
                defend_with="armor",
                hindrance=hindrance,
            ),
            seed=2,
        )
    assert player.alive
    assert player.require_sheet().items["armor"].broken
    assert player.require_sheet().hindrances == ["a bruised rib", "a ringing ear", "a torn sleeve"]
    with pytest.raises(Refusal, match="already broken"):
        _ = _rolled(
            draft,
            Roll(
                what="Take fire",
                skill="Stealth",
                risk="a bullet",
                defend_with="armor",
                hindrance="a fourth wound",
            ),
            seed=2,
        )


def test_defend_with_non_harmless_gear_and_no_hindrance_is_refused_before_any_dice_roll() -> None:
    draft = small_world().draft()
    before = draft.model_copy(deep=True)
    with pytest.raises(Refusal, match="name the hindrance Lockpick set leaves behind"):
        _ = _rolled(
            draft,
            Roll(what="Sneak past", skill="Stealth", risk="a guard's knife", defend_with=LOCKPICKS),
            seed=2,
        )
    assert draft.payload == before.payload


def test_defend_with_harmless_gear_and_a_hindrance_is_refused_before_any_dice_roll() -> None:
    draft = small_world().draft()
    before = draft.model_copy(deep=True)
    with pytest.raises(Refusal, match="breaks harmlessly: leave `hindrance` empty"):
        _ = _rolled(
            draft,
            Roll(
                what="Weather the blast",
                skill="Stealth",
                risk="shrapnel",
                defend_with="hull-armor",
                hindrance="a dent",
            ),
            seed=2,
        )
    assert draft.payload == before.payload


def test_deadly_setback_with_defend_with_breaks_gear_instead_of_maiming(
    draft: TwentyfourxxGame,
) -> None:
    player = draft.payload.player
    facts = _rolled(
        draft,
        Roll(
            what="Sneak past",
            skill="Stealth",
            risk="a guard's knife",
            deadly=True,
            defend_with=LOCKPICKS,
            hindrance="cut fingers",
        ),
        seed=1,
    )
    assert player.require_sheet().items[LOCKPICKS].broken
    assert player.require_sheet().hindrances == ["cut fingers"]
    assert not any(fact.card == "Hindered: Maimed" for fact in facts)


def test_non_deadly_setback_with_defend_with_costs_nothing(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    facts = _rolled(
        draft,
        Roll(
            what="Sneak past",
            skill="Stealth",
            risk="a guard's knife",
            defend_with=LOCKPICKS,
            hindrance="cut fingers",
        ),
        seed=1,
    )
    assert player.require_sheet().items[LOCKPICKS].broken_times == 0
    assert player.require_sheet().hindrances == []
    assert len(facts) == 2


def test_helper_defends_with_their_own_gear_while_actor_takes_their_own_consequence() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 10}).draft()
    draft.payload.cast[KESTREL].require_sheet().items["vest"] = Gear(name="Vest")
    player = draft.payload.player
    member = draft.payload.cast[KESTREL]
    facts = _rolled(
        draft,
        Roll(
            what="Slip past",
            skill="Stealth",
            risk="a guard's knife",
            helped_by=Helper(
                actor_id=KESTREL,
                risk="crossfire",
                deadly=True,
                defend_with="vest",
                hindrance="ringing ears",
            ),
        ),
        seed=15,
    )
    assert player.alive
    assert player.require_sheet().hindrances == []
    assert member.alive
    assert member.require_sheet().items["vest"].broken_times == 1
    assert member.require_sheet().hindrances == ["ringing ears"]
    assert any(fact.card == "Kestrel: Vest breaks — ringing ears" for fact in facts)


def test_both_participants_defend_with_their_own_separate_items(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Stealth": 10}).draft()
    draft.payload.cast[KESTREL].require_sheet().items["vest"] = Gear(name="Vest")
    player = draft.payload.player
    member = draft.payload.cast[KESTREL]
    facts = _rolled(
        draft,
        Roll(
            what="Slip past",
            skill="Stealth",
            risk="a guard's knife",
            defend_with=LOCKPICKS,
            hindrance="cut fingers",
            helped_by=Helper(
                actor_id=KESTREL, risk="crossfire", defend_with="vest", hindrance="ringing ears"
            ),
        ),
        seed=2,
    )
    assert player.alive
    assert player.require_sheet().items[LOCKPICKS].broken_times == 1
    assert player.require_sheet().hindrances == ["cut fingers"]
    assert member.alive
    assert member.require_sheet().items["vest"].broken_times == 1
    assert member.require_sheet().hindrances == ["ringing ears"]
    assert any(fact.card == "Lockpick set breaks — cut fingers" for fact in facts)
    assert any(fact.card == "Kestrel: Vest breaks — ringing ears" for fact in facts)


def test_both_participants_naming_the_same_ship_function_are_refused_before_any_dice_roll() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 10}).draft()
    before = draft.model_copy(deep=True)
    with pytest.raises(Refusal, match="already broken"):
        _ = _rolled(
            draft,
            Roll(
                what="Take fire",
                skill="Stealth",
                risk="shrapnel",
                defend_with="weapons",
                hindrance="a jammed weapon",
                helped_by=Helper(
                    actor_id=KESTREL,
                    risk="shrapnel",
                    defend_with="weapons",
                    hindrance="a scorched hand",
                ),
            ),
            seed=2,
        )
    assert draft.payload == before.payload


def test_helper_with_risk_takes_their_own_consequence_on_a_bad_roll() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 10}).draft()
    facts = _rolled(
        draft,
        Roll(
            what="Slip past",
            skill="Stealth",
            helped_by=Helper(actor_id=KESTREL, risk="a guard's knife", deadly=True),
        ),
        seed=2,
    )
    member = draft.payload.cast[KESTREL]
    assert draft.payload.player.alive
    assert not member.alive
    assert any(fact.card == f"{member.name} is dead" for fact in facts)


def test_helper_with_no_risk_is_untouched_on_a_bad_roll(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Stealth": 10}).draft()
    _ = _rolled(
        draft, Roll(what="Slip past", skill="Stealth", helped_by=Helper(actor_id=KESTREL)), seed=2
    )
    member = draft.payload.cast[KESTREL]
    assert draft.payload.player.alive
    assert member.alive


def test_hindered_helper_contributes_d4(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Stealth": 8}).draft()
    facts = _rolled(
        draft,
        Roll(
            what="Slip past",
            skill="Stealth",
            helped_by=Helper(actor_id=KESTREL, hindered="a bad leg"),
        ),
    )
    assert facts[1].dice[0].faces == (10, 4)
    assert "hindered" in facts[1].trace


def test_succession_runs_only_after_both_the_actor_and_helper_consequences_land() -> None:
    state = hired(small_world(), KESTREL, skills={"Stealth": 10})
    state.payload.cast[SABLE].known = True
    state = hired(state, SABLE, skills={"Stealth": 8})
    draft = state.draft()
    facts = _rolled(
        draft,
        Roll(
            what="Slip past",
            skill="Stealth",
            risk="a guard's knife",
            deadly=True,
            helped_by=Helper(actor_id=KESTREL, risk="crossfire", deadly=True),
        ),
        seed=2,
    )
    assert not draft.payload.player.alive
    assert not draft.payload.cast[KESTREL].alive
    assert draft.payload.cast[SABLE].alive
    assert draft.pending is not None
    assert draft.pending.kind == "succession"
    assert [option.id for option in draft.pending.options] == [SABLE]
    assert any(fact.card == f"{draft.payload.cast[KESTREL].name} is dead" for fact in facts)


def test_defend_with_needs_a_risk_on_roll_and_helper() -> None:
    with pytest.raises(ValueError, match="defend_with needs the risk"):
        _ = Roll(what="Sneak past", defend_with=LOCKPICKS)
    with pytest.raises(ValueError, match="defend_with needs the risk"):
        _ = Helper(actor_id=KESTREL, defend_with=LOCKPICKS)


def test_hindrance_needs_a_defend_with_on_roll_and_helper() -> None:
    with pytest.raises(ValueError, match="hindrance needs the defend_with"):
        _ = Roll(what="Sneak past", hindrance="cut fingers")
    with pytest.raises(ValueError, match="hindrance needs the defend_with"):
        _ = Helper(actor_id=KESTREL, hindrance="cut fingers")


def test_deadly_needs_a_risk_on_roll_and_helper() -> None:
    with pytest.raises(ValueError, match="deadly needs the risk"):
        _ = Roll(what="Sneak past", deadly=True)
    with pytest.raises(ValueError, match="deadly needs the risk"):
        _ = Helper(actor_id=KESTREL, deadly=True)


def test_ask_world_facts_are_untold(draft: TwentyfourxxGame) -> None:
    dice_fact, luck_fact = ENGINE.ask_world(draft, AskWorld(question="Is anyone home?"), Random(0))
    assert not dice_fact.told
    assert not luck_fact.told
    assert luck_fact.card == ""


def test_defend_breaks_the_item_and_adds_the_hindrance_refused_when_broken() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    facts = change(ENGINE, draft, "defend", item_id=LOCKPICKS, hindrance="fingers cut")
    assert player.require_sheet().items[LOCKPICKS].broken_times == 1
    assert player.require_sheet().items[LOCKPICKS].broken
    assert "fingers cut" in player.require_sheet().hindrances
    assert any(fact.card == "Lockpick set breaks — fingers cut" for fact in facts)

    assert "already broken" in refused(
        ENGINE, draft, "defend", item_id=LOCKPICKS, hindrance="fingers cut again"
    )


def test_defend_refuses_an_empty_hindrance_on_a_carried_item(draft: TwentyfourxxGame) -> None:
    assert "name the hindrance" in refused(ENGINE, draft, "defend", item_id=LOCKPICKS)


def test_defend_hull_armor_breaks_harmlessly_and_refuses_a_hindrance() -> None:
    draft = small_world().draft()
    facts = change(ENGINE, draft, "defend", item_id="hull-armor")
    assert draft.payload.ship["hull-armor"].broken
    assert draft.payload.player.require_sheet().hindrances == []
    assert any(fact.card == "Hull armor breaks" for fact in facts)

    draft = small_world().draft()
    assert "leave `hindrance` empty" in refused(
        ENGINE, draft, "defend", item_id="hull-armor", hindrance="hull breached"
    )


def test_defend_refuses_naming_an_unmet_entity_but_allows_a_revealed_one(
    draft: TwentyfourxxGame,
) -> None:
    player = draft.payload.player
    assert "not met" in refused(
        ENGINE, draft, "defend", item_id=LOCKPICKS, hindrance="marked by Sable"
    )
    assert player.require_sheet().items[LOCKPICKS].broken_times == 0

    _ = change(ENGINE, draft, "defend", item_id=LOCKPICKS, hindrance="marked by Kestrel")
    assert player.require_sheet().items[LOCKPICKS].broken_times == 1


def test_gain_item_spends_and_refuses_short_credits(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    assert player.require_sheet().credits == STARTING_CREDITS
    _ = change(ENGINE, draft, "gain_item", name="Rope", cost=1)
    assert player.require_sheet().credits == STARTING_CREDITS - 1
    assert player.require_sheet().items["rope"].name == "Rope"

    assert "only" in refused(ENGINE, draft, "gain_item", name="Grenade", cost=99)


def test_gain_item_slugs_against_the_ships_functions_too(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    _ = change(ENGINE, draft, "gain_item", name="Sensors")
    assert "sensors" not in player.require_sheet().items
    assert player.require_sheet().items["sensors-2"].name == "Sensors"
    assert draft.payload.ship["sensors"].name == "Sensors"


def test_gain_item_refuses_naming_an_unmet_entity_but_allows_a_revealed_one(
    draft: TwentyfourxxGame,
) -> None:
    player = draft.payload.player
    assert "not met" in refused(ENGINE, draft, "gain_item", name="Sable's shiv")
    assert not any(item.name == "Sable's shiv" for item in player.require_sheet().items.values())

    _ = change(ENGINE, draft, "gain_item", name="Kestrel's rope")
    assert any(item.name == "Kestrel's rope" for item in player.require_sheet().items.values())


def test_a_hired_members_kit_slugs_against_the_ships_functions_too() -> None:
    made = items_from_kits([Kit(name="Sensors"), Kit(name="Hull armor"), Kit(name="Rope")])
    assert [key for key in made if key in SHIP_IDS] == []
    assert made["sensors-2"].name == "Sensors"


def test_spend_refuses_short_credits(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    _ = change(ENGINE, draft, "spend", amount=1, why="a bribe")
    assert player.require_sheet().credits == STARTING_CREDITS - 1
    assert "only" in refused(ENGINE, draft, "spend", amount=99, why="a bigger bribe")


def test_spend_with_actor_id_pays_from_the_member_credits(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Shooting": 8}).draft()
    member = draft.payload.cast[KESTREL]
    before = member.require_sheet().credits
    _ = change(ENGINE, draft, "spend", amount=1, why="ammo", actor_id=KESTREL)
    assert member.require_sheet().credits == before - 1
    assert draft.payload.player.require_sheet().credits == STARTING_CREDITS


def test_spend_refuses_naming_an_unmet_entity_but_allows_a_revealed_one(
    draft: TwentyfourxxGame,
) -> None:
    player = draft.payload.player
    assert "not met" in refused(ENGINE, draft, "spend", amount=1, why="a bribe for Sable")
    assert player.require_sheet().credits == STARTING_CREDITS

    _ = change(ENGINE, draft, "spend", amount=1, why="a bribe for Kestrel")
    assert player.require_sheet().credits == STARTING_CREDITS - 1


def test_repair_item_zeroes_broken_times_and_refuses_an_unbroken_item() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    assert "not broken" in refused(ENGINE, draft, "repair_item", item_id=LOCKPICKS)

    player.require_sheet().items[LOCKPICKS].broken_times = 1
    _ = change(ENGINE, draft, "repair_item", item_id=LOCKPICKS)
    assert player.require_sheet().items[LOCKPICKS].broken_times == 0


def test_change_hindrances_gains_and_loses_refuses_duplicate_and_absent() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    _ = change(ENGINE, draft, "change_hindrances", gained=["Bleeding"])
    assert player.require_sheet().hindrances == ["Bleeding"]

    assert "already" in refused(ENGINE, draft, "change_hindrances", gained=["Bleeding"])
    assert "carries no" in refused(ENGINE, draft, "change_hindrances", lost=["Scared"])

    _ = change(ENGINE, draft, "change_hindrances", gained=["Scared"], lost=["Bleeding"])
    assert player.require_sheet().hindrances == ["Scared"]


def test_change_hindrances_refuses_naming_an_unmet_entity_but_allows_a_revealed_one(
    draft: TwentyfourxxGame,
) -> None:
    player = draft.payload.player
    assert "not met" in refused(ENGINE, draft, "change_hindrances", gained=["Marked by Sable"])
    assert player.require_sheet().hindrances == []

    _ = change(ENGINE, draft, "change_hindrances", gained=["Marked by Kestrel"])
    assert player.require_sheet().hindrances == ["Marked by Kestrel"]


def test_finish_job_raises_a_skill_enters_a_new_one_refuses_at_d12_adds_credits() -> None:
    draft = small_world().draft()
    player = draft.payload.player
    before_credits = player.require_sheet().credits

    draft.payload.job = "Escort the crate to dock nine"
    facts = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))
    assert player.require_sheet().skills["Stealth"] == 12
    assert player.require_sheet().credits == before_credits + 4
    assert any(fact.card == "Job done: Stealth d12" for fact in facts)
    assert draft.payload.job == ""

    draft.payload.job = "Shadow the courier"
    _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Climbing"),)), Random(1))
    assert player.require_sheet().skills["Climbing"] == 8

    draft.payload.job = "One skill too far"
    with pytest.raises(Refusal, match="Rook's Stealth is already at d12"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))


def test_finish_job_names_a_skill_nobody_has_and_adds_it_at_d8(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    draft.payload.job = "Improvise a bypass"
    facts = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Sabotage"),)), Random(0))
    assert player.require_sheet().skills["Sabotage"] == 8
    assert any(fact.card == "Job done: Sabotage d8" for fact in facts)


def test_finish_job_names_lowercase_stealth_and_raises_the_existing_key() -> None:
    draft = hired(small_world(), KESTREL, skills={"Stealth": 8}).draft()
    member = draft.payload.cast[KESTREL]
    draft.payload.job = "Escort the crate"
    _ = ENGINE.job(
        draft,
        Job(
            verb="finish",
            raises=(Raise(skill="Stealth"), Raise(actor_id=KESTREL, skill="stealth")),
        ),
        Random(0),
    )
    assert member.require_sheet().skills == {"Stealth": 10}
    assert len(member.require_sheet().skills) == 1


def test_finish_job_names_a_hired_members_skill_when_already_at_d12() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 12}).draft()
    draft.payload.job = "Escort the crate"
    with pytest.raises(Refusal, match="Kestrel's Shooting is already at d12"):
        _ = ENGINE.job(
            draft,
            Job(
                verb="finish",
                raises=(Raise(skill="Stealth"), Raise(actor_id=KESTREL, skill="Shooting")),
            ),
            Random(0),
        )


def test_finish_job_refuses_raises_missing_a_hired_member(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Shooting": 8}).draft()
    draft.payload.job = "Escort the crate"
    with pytest.raises(Refusal, match="the player and every living hired member"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))


def test_finish_job_refuses_raises_that_name_the_player_twice(draft: TwentyfourxxGame) -> None:
    draft.payload.job = "Escort the crate"
    with pytest.raises(Refusal, match="given player, player"):
        _ = ENGINE.job(
            draft,
            Job(verb="finish", raises=(Raise(skill="Stealth"), Raise(skill="Climbing"))),
            Random(0),
        )


def test_finish_job_raises_the_whole_crew_and_pays_each_a_d6(draft: TwentyfourxxGame) -> None:
    draft = hired(draft, KESTREL, skills={"Shooting": 8}).draft()
    player = draft.payload.player
    member = draft.payload.cast[KESTREL]
    before_member_credits = member.require_sheet().credits
    draft.payload.job = "Escort the crate"

    facts = ENGINE.job(
        draft,
        Job(
            verb="finish",
            raises=(Raise(skill="Stealth"), Raise(actor_id=KESTREL, skill="Shooting")),
        ),
        Random(0),
    )

    assert player.require_sheet().skills["Stealth"] == 12
    assert member.require_sheet().skills["Shooting"] == 10
    assert member.require_sheet().credits > before_member_credits
    assert any(fact.card == "Kestrel: Job done: Shooting d10" for fact in facts)


def test_android_case_is_an_item_on_creation_and_defend_breaks_it_harmlessly() -> None:
    picks = {
        "specialty": "tech",
        "origin": "android",
        "increase-1": "climbing",
        "body": "case",
    }
    character = ENGINE.create_character("Unit-9", "A tireless drone", picks)
    android = character.payload
    sheet = android.require_sheet()
    case_id = next(item_id for item_id, item in sheet.items.items() if item.name == "Case")

    draft = small_world().draft()
    draft.payload.player = android

    facts = change(ENGINE, draft, "defend", item_id=case_id)
    assert draft.payload.player.require_sheet().items[case_id].broken
    assert draft.payload.player.require_sheet().hindrances == []
    assert any(fact.card == "Case breaks" for fact in facts)


def test_take_job_opens_a_job_and_refuses_a_second_while_open(draft: TwentyfourxxGame) -> None:
    facts = ENGINE.job(draft, Job(verb="take", terms="Move the crates by dawn"), Random(0))
    assert draft.payload.job == "Move the crates by dawn"
    assert any(fact.card == "Job taken\nMove the crates by dawn" for fact in facts)

    with pytest.raises(Refusal, match="a job is open"):
        _ = ENGINE.job(draft, Job(verb="take", terms="A second job"), Random(0))


def test_job_take_refuses_naming_an_unmet_entity_but_allows_a_revealed_one(
    draft: TwentyfourxxGame,
) -> None:
    assert "not met" in refused(ENGINE, draft, "job", verb="take", terms="Steal from Sable")
    assert draft.payload.job == ""

    _ = change(ENGINE, draft, "job", verb="take", terms="Steal from Kestrel")
    assert draft.payload.job == "Steal from Kestrel"


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


def test_find_job_refused_while_a_job_is_open(draft: TwentyfourxxGame) -> None:
    draft.payload.job = "Move the crates by dawn"
    with pytest.raises(Refusal, match="a job is open"):
        _ = ENGINE.job(draft, Job(verb="find", where="Docks"), Random(0))


def test_job_find_refuses_naming_an_unmet_entity_but_allows_a_revealed_one(
    draft: TwentyfourxxGame,
) -> None:
    assert "not met" in refused(ENGINE, draft, "job", verb="find", where="Ask Sable's contact")

    facts = change(ENGINE, draft, "job", verb="find", where="Ask Kestrel's contact")
    assert "Ask Kestrel's contact" in facts[1].trace


def test_finish_job_refuses_without_a_job_open(draft: TwentyfourxxGame) -> None:
    with pytest.raises(Refusal, match="no job is open"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))


def test_finish_job_pays_once_and_refuses_a_second_call(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    before_credits = player.require_sheet().credits

    draft.payload.job = "Deliver the package"
    _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))
    assert player.require_sheet().credits == before_credits + 4
    assert draft.payload.job == ""

    with pytest.raises(Refusal, match="no job is open"):
        _ = ENGINE.job(draft, Job(verb="finish", raises=(Raise(skill="Stealth"),)), Random(0))
    assert player.require_sheet().credits == before_credits + 4


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


def test_kill_on_the_player_flips_player_over(draft: TwentyfourxxGame) -> None:
    facts = change(ENGINE, draft, "kill", entity_id=PLAYER_ID)
    assert not draft.payload.player.alive
    assert ENGINE.over(draft) == "You died."
    assert any(fact.card == "You are dead" for fact in facts)


def test_risk_disaster_with_hired_member_sets_succession_and_over_stays_none() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    facts = _rolled(
        draft, Roll(what="Slip past", skill="Stealth", risk="a long fall", deadly=True), seed=2
    )
    assert not draft.payload.player.alive
    assert draft.pending is not None
    assert draft.pending.kind == "succession"
    assert [option.id for option in draft.pending.options] == [KESTREL]
    assert ENGINE.over(draft) is None
    assert any(fact.card == "You are dead" for fact in facts)


def test_kill_on_the_lead_with_a_hired_member_opens_the_succession() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    _ = change(ENGINE, draft, "kill", entity_id=PLAYER_ID)
    assert draft.pending is not None
    assert draft.pending.kind == "succession"
    assert ENGINE.over(draft) is None


def test_risk_disaster_with_none_hired_ends_the_game(draft: TwentyfourxxGame) -> None:
    _ = _rolled(
        draft, Roll(what="Slip past", skill="Stealth", risk="a long fall", deadly=True), seed=2
    )
    assert not draft.payload.player.alive
    assert draft.pending is None
    assert ENGINE.over(draft) == "You died."


def test_answering_the_succession_decision_makes_the_member_the_player() -> None:
    draft = hired(small_world(), KESTREL, skills={"Shooting": 8}).draft()
    _ = _rolled(
        draft, Roll(what="Slip past", skill="Stealth", risk="a long fall", deadly=True), seed=2
    )
    assert draft.pending is not None
    option = draft.pending.options[0]
    facts = ENGINE.answer(draft, option, Random(0))
    assert draft.payload.player.id == KESTREL
    assert any(fact.card == "Kestrel leads now" for fact in facts)


def test_ship_upgrade_pays_credits_once_and_refuses_a_second(draft: TwentyfourxxGame) -> None:
    player = draft.payload.player
    player.require_sheet().credits = UPGRADE_COST * 2
    before = player.require_sheet().credits
    facts = change(ENGINE, draft, "ship_upgrade", function_id="hull-armor")
    assert player.require_sheet().credits == before - UPGRADE_COST
    assert draft.payload.ship["hull-armor"].upgraded
    assert any(fact.card == "Hull armor upgraded — ₡10" for fact in facts)

    assert "already" in refused(ENGINE, draft, "ship_upgrade", function_id="hull-armor")


def test_defend_and_repair_item_on_the_ships_hull_armor(draft: TwentyfourxxGame) -> None:
    _ = change(ENGINE, draft, "defend", item_id="hull-armor")
    assert draft.payload.ship["hull-armor"].broken

    _ = change(ENGINE, draft, "repair_item", item_id="hull-armor")
    assert not draft.payload.ship["hull-armor"].broken


def test_next_scene_offers_the_way_on_and_refuses_a_second_offer(draft: TwentyfourxxGame) -> None:
    _ = ENGINE.next_scene(draft, NextScene(), Random(0))
    assert draft.payload.run.offered
    with pytest.raises(Refusal, match="already offers"):
        _ = ENGINE.next_scene(draft, NextScene(), Random(0))


def test_leave_takes_a_cast_member_out(draft: TwentyfourxxGame) -> None:
    assert "leaves" in change(ENGINE, draft, "leave", entity_id=KESTREL)[0].trace
