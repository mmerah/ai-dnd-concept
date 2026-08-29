from pathlib import Path
from random import Random

import pytest
from core_test_support import (
    ENGINES_BUILT,
    TWENTYFOURXX,
    at_boundary,
    game,
    sheet_of,
)
from pydantic import ValidationError

from aidm.engines.core import (
    Engine,
    complete_chapter,
    rules,
    take_over,
)
from aidm.engines.twentyfourxx.engine import advance, build
from aidm.engines.twentyfourxx.rules import (
    RULES,
    Advance,
    Attempt,
    Defence,
    ItemSheet,
    LuckTest,
    Sheet,
    StakedAttempt,
    apply_change_credits,
    outcome_for,
    pool_faces,
    resolve_attempt,
    resolve_defence,
    resolve_luck_test,
    resolve_stake,
)
from aidm.state.creation import Picks
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import Fact, player_events
from aidm.state.model import Game
from aidm.state.play import DecisionOption, PendingDecision

ALLY = EntityId("ovid-sarn")
LANTERN = EntityId("lantern")
RISK = "The hinges may take your hand with them."
# The seed on which Kael's own attempt is a disaster: the hit that hands him the defence.
HIT = 2


@pytest.mark.parametrize(
    ("skill", "helped", "hindered", "expected"),
    [
        ("", "", "", (6,)),
        ("Climbing", "", "", (10,)),
        ("Climbing", "a steady rope", "", (10, 6)),
        ("Climbing", "", "the rotten rung", (4,)),
        ("Climbing", "a steady rope", "the rotten rung", (4, 6)),
    ],
)
def test_the_die_pool_is_built_from_the_sheet_help_and_hindrance(
    skill: str, helped: str, hindered: str, expected: tuple[int, ...]
) -> None:
    sheet = Sheet(skills={"Climbing": 10})
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="climb the wall",
        risk=RISK,
        hit=True,
        skill=skill,
        helped=helped,
        hindered=hindered,
    )
    assert pool_faces(sheet, action, None) == expected


def test_a_helper_rolls_their_own_skill_die_into_the_pool() -> None:
    sheet = Sheet(skills={"Climbing": 10})
    helper = Sheet(skills={"Hacking": 12})
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="climb the wall",
        risk=RISK,
        hit=True,
        skill="Climbing",
        helper_id=ALLY,
        helper_skill="Hacking",
    )
    assert pool_faces(sheet, action, helper) == (10, 12)


@pytest.mark.parametrize(
    ("kept", "expected"),
    [
        (1, "disaster"),
        (2, "disaster"),
        (3, "setback"),
        (4, "setback"),
        (5, "success"),
        (6, "success"),
    ],
)
def test_the_outcome_ladder_maps_the_kept_die_to_a_result(kept: int, expected: str) -> None:
    assert outcome_for(kept) == expected


def test_an_attempt_is_refused_before_it_rolls_when_the_skill_is_not_on_the_sheet() -> None:
    _, state = game(TWENTYFOURXX)

    unknown_skill = Attempt(
        actor_id=PLAYER_ID, goal="Kael picks the lock.", risk=RISK, hit=False, skill="Lockpicking"
    )
    with pytest.raises(ValueError) as skill_error:
        resolve_attempt(state.draft(), unknown_skill, Random(0))
    message = str(skill_error.value)
    assert "Climbing" in message
    assert "Stealth" in message
    assert "Tracking" in message


def test_an_ally_who_lacks_the_named_skill_is_refused() -> None:
    _, state = game(TWENTYFOURXX)
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="Kael picks the lock while Ovid covers the door.",
        risk=RISK,
        hit=False,
        helper_id=ALLY,
        helper_skill="Lockpicking",
    )
    with pytest.raises(ValueError, match="helper_skill"):
        resolve_attempt(state.draft(), action, Random(0))


def test_naming_both_an_ally_and_a_helped_tag_is_refused_at_the_schema() -> None:
    with pytest.raises(ValidationError):
        Attempt(
            actor_id=PLAYER_ID,
            goal="Kael picks the lock.",
            risk=RISK,
            hit=False,
            helper_id=ALLY,
            helped="a steady rope",
        )


def test_a_job_raises_one_skill_a_step_and_pays_rolled_credits() -> None:
    engine, state = game(TWENTYFOURXX)
    assert engine.owed_notes(state) == ()

    ready = at_boundary(state, Sheet)
    (owed,) = engine.owed_notes(ready)
    assert ready.player.name in owed
    before = sheet_of(ready, PLAYER_ID, Sheet)

    raise_existing = Advance(
        subject_id=PLAYER_ID, skill="Tracking", why="the climb taught them the route"
    )
    draft = ready.draft()
    facts = advance(draft, raise_existing, Random(3))
    grown = draft.committed()

    sheet = sheet_of(grown, PLAYER_ID, Sheet)
    assert sheet.skills["Tracking"] == 10
    assert sheet.jobs == before.jobs + 1
    (dice_fact,) = [fact for fact in facts if fact.kind == "dice_rolled"]
    paid = sheet.credits.current - before.credits.current
    assert dice_fact.trace.endswith(f"-> {paid}")

    take_new = Advance(subject_id=PLAYER_ID, skill="Lockpicking", why="the job called for it")
    draft = ready.draft()
    _ = advance(draft, take_new, Random(4))
    assert sheet_of(draft.committed(), PLAYER_ID, Sheet).skills["Lockpicking"] == 8


def test_a_companion_without_a_sheet_earns_no_chapter_and_cannot_be_played_on() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    ally = draft.world.require(ALLY)
    ally.rules, ally.known, ally.parent_id = {}, True, draft.player_location
    draft.world.party.append(ALLY)
    _ = complete_chapter(draft, "the job is done", Sheet)
    joined = draft.committed()

    assert joined.world.require(ALLY).rules == {}
    (owed,) = engine.owed_notes(joined)
    assert joined.player.name in owed

    handed = joined.draft()
    _ = take_over(handed, ALLY)
    with pytest.raises(ValueError, match="no character sheet"):
        engine.validate(handed)


def test_a_skill_already_at_d12_is_refused_with_the_engines_own_reason() -> None:
    _, state = game(TWENTYFOURXX)
    draft = at_boundary(state, Sheet).draft()
    with rules(draft.world.require(PLAYER_ID), Sheet) as sheet:
        sheet.skills["Climbing"] = 12
    maxed = draft.committed()

    capped = Advance(subject_id=PLAYER_ID, skill="Climbing", why="there is nowhere higher to climb")
    with pytest.raises(ValueError, match="d12"):
        _ = advance(maxed.draft(), capped, Random(0))


def test_credits_are_paid_charged_and_never_overdrawn() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()
    before = sheet_of(draft, PLAYER_ID, Sheet).credits.current

    paid = apply_change_credits(draft, PLAYER_ID, 3)
    assert [fact.kind for fact in paid] == ["counter_changed"]
    assert sheet_of(draft, PLAYER_ID, Sheet).credits.current == before + 3

    with pytest.raises(ValueError, match="cannot be spent"):
        _ = apply_change_credits(draft, PLAYER_ID, -(before + 4))
    assert sheet_of(draft, PLAYER_ID, Sheet).credits.current == before + 3

    with pytest.raises(ValueError, match="zero moves nothing"):
        _ = apply_change_credits(draft, PLAYER_ID, 0)


def _tested(resolution: tuple[Fact, ...]) -> Fact:
    return next(fact for fact in resolution if fact.kind == "luck_tested")


def test_a_tested_bad_luck_risk_that_lands_leaves_a_note_for_the_next_turn() -> None:
    _, state = game(TWENTYFOURXX)
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="Kael tries something risky.",
        risk=RISK,
        hit=True,
        luck_test="running out of oil",
    )

    draft = state.draft()
    facts = resolve_attempt(draft, action, Random(2))
    (card,) = player_events(facts)
    luck = next(die for die in card.dice if die.label == "Luck")
    assert 1 <= luck.kept <= 4
    assert len(draft.world.pending_notes) == 1
    assert any(fact.kind == "luck_tested" for fact in facts)

    draft = state.draft()
    facts = resolve_attempt(draft, action, Random(1))
    assert draft.world.pending_notes == state.world.pending_notes == ()
    assert not any(fact.kind == "luck_tested" for fact in facts)


def test_a_standalone_luck_test_needs_no_attempt_and_only_bad_luck_leaves_a_note() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")

    draft = state.draft()
    trouble = resolve_luck_test(draft, action, Random(2))
    assert _tested(trouble).trace.endswith(": trouble")
    assert len(draft.world.pending_notes) == 1

    signs = resolve_luck_test(state.draft(), action, Random(0))
    assert _tested(signs).trace.endswith(": signs of it")

    draft = state.draft()
    clear = resolve_luck_test(draft, action, Random(5))
    assert not any(fact.kind == "luck_tested" for fact in clear)
    assert draft.world.pending_notes == ()


def _forcing(**args: object) -> Attempt:
    return Attempt.model_validate(
        {
            "actor_id": PLAYER_ID,
            "goal": "Kael forces the vault door",
            "risk": RISK,
            "hit": True,
            "skill": "Climbing",
        }
        | args
    )


def _staked_forcing(**args: object) -> StakedAttempt:
    return StakedAttempt.model_validate(
        {
            "actor_id": PLAYER_ID,
            "goal": "Kael forces the vault door",
            "risk": RISK,
            "hit": True,
            "skill": "Climbing",
        }
        | args
    )


def _waiting(draft: Game) -> PendingDecision:
    decision = draft.pending
    assert decision is not None
    return decision


def _hit(state: Game) -> tuple[Game, PendingDecision]:
    """A draft carrying the defence decision Kael's own disaster opened, ready to be answered."""
    draft = state.draft()
    _ = resolve_attempt(draft, _forcing(), Random(HIT))
    decision = _waiting(draft)
    draft.pending = None
    return draft, decision


def test_a_stake_freezes_a_playable_attempt_and_waits_on_the_player() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    assert resolve_stake(draft, _staked_forcing()) == ()

    decision = _waiting(draft)
    assert decision.kind == "stake"
    assert decision.prompt.startswith(RISK)
    assert [option.id for option in decision.options] == ["proceed"]
    assert StakedAttempt.model_validate(decision.payload) == _staked_forcing()


def test_an_actor_attempt_cannot_be_staked() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    with pytest.raises(ValueError, match="stake only the player's attempt"):
        _ = resolve_stake(draft, _staked_forcing(actor_id=ALLY))
    assert draft.pending is None


def test_a_stake_on_an_attempt_the_sheet_cannot_carry_freezes_nothing() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    with pytest.raises(ValueError, match="no skill 'Lockpicking'"):
        _ = resolve_stake(draft, _staked_forcing(skill="Lockpicking"))
    assert draft.pending is None


def test_proceeding_rolls_the_frozen_attempt_and_a_hit_hands_back_the_defence() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    _ = resolve_stake(draft, _staked_forcing())
    staked = _waiting(draft)
    draft.pending = None

    facts = engine.resume(draft, staked, "proceed", Random(HIT))

    (resolved,) = [fact for fact in facts if fact.kind == "attempt_resolved"]
    assert resolved.trace.endswith("-> disaster")
    decision = _waiting(draft)
    assert decision.kind == "defence"
    assert [option.id for option in decision.options] == ["lantern", "take-it"]
    assert Defence.model_validate(decision.payload) == Defence(goal=_forcing().goal)


def test_breaking_an_item_turns_the_hit_and_that_item_is_never_offered_again() -> None:
    engine, state = game(TWENTYFOURXX)
    draft, decision = _hit(state)

    facts = engine.resume(draft, decision, "lantern", Random(0))

    assert [fact.kind for fact in facts] == ["defence_turned"]
    assert sheet_of(draft, LANTERN, ItemSheet).broken
    _ = resolve_attempt(draft, _forcing(), Random(HIT))
    assert [option.id for option in _waiting(draft).options] == ["take-it"]


def test_taking_the_hit_records_it_landing_in_full() -> None:
    engine, state = game(TWENTYFOURXX)
    draft, decision = _hit(state)

    (landed,) = engine.resume(draft, decision, "take-it", Random(0))

    assert landed.kind == "defence_taken"
    assert landed.told
    assert draft.world.require(LANTERN).rules == {}
    assert draft.pending is None


def test_only_a_hit_hands_the_player_a_defence() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    _ = resolve_attempt(draft, _forcing(hit=False), Random(HIT))
    assert draft.pending is None

    _ = resolve_attempt(draft, _forcing(), Random(HIT))
    assert _waiting(draft).kind == "defence"


def test_an_actors_failed_hit_hands_the_player_no_defence() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    facts = resolve_attempt(
        draft, Attempt(actor_id=ALLY, goal="Ovid shoulders it", risk=RISK, hit=True), Random(HIT)
    )

    (resolved,) = [fact for fact in facts if fact.kind == "attempt_resolved"]
    assert resolved.entity_id == ALLY
    assert resolved.trace.endswith("-> disaster")
    assert draft.pending is None


def _bought(
    engine: Engine, draft: Game, gear_id: str, onto_id: str | None = None
) -> tuple[Fact, ...]:
    buy = next(one for one in engine.director_tools if one.name == "buy_gear")
    return buy.call(
        draft, {"actor_id": "player", "gear_id": gear_id, "onto_id": onto_id}, Random(0)
    )


def test_gear_that_breaks_three_times_holds_twice_before_it_is_broken() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    assert _bought(engine, draft, "battle-armor")
    armor = draft.world.require(EntityId("battle-armor"))

    for left in (2, 1):
        held = resolve_defence(draft, "Kael takes the burst", armor.id)
        assert [fact.kind for fact in held] == ["defence_turned"]
        sheet = sheet_of(draft, armor.id, ItemSheet)
        assert sheet.breaks.current == left
        assert not sheet.broken

    spent = resolve_defence(draft, "Kael takes the burst", armor.id)
    assert [fact.kind for fact in spent] == ["defence_turned"]
    sheet = sheet_of(draft, armor.id, ItemSheet)
    assert sheet.broken and sheet.breaks.current == 0


def test_an_items_marks_reach_the_prompt_as_its_own_state_lines() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    assert _bought(engine, draft, "battle-armor")

    armor = draft.world.require(EntityId("battle-armor"))
    assert engine.describe(draft, armor) == "bulky: yes\nbreaks left: 3"
    _ = resolve_defence(draft, "Kael takes the burst", armor.id)
    assert engine.describe(draft, armor) == "bulky: yes\nbreaks left: 2"
    assert engine.describe(draft, draft.world.require(LANTERN)) == ""


def test_a_second_purchase_of_the_same_gear_is_charged_and_lands_beside_the_first() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    before = sheet_of(draft, PLAYER_ID, Sheet).credits.current

    for _ in range(2):
        assert _bought(engine, draft, "pistol")

    carried = [item.id for item in draft.world.children(PLAYER_ID, "item")]
    assert "pistol" in carried and "pistol-2" in carried
    assert sheet_of(draft, PLAYER_ID, Sheet).credits.current == before - 2


def test_a_ship_upgrade_is_charged_at_ten_and_installed_in_the_ship() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    ship = draft.player_location
    _ = apply_change_credits(draft, PLAYER_ID, RULES.ship_upgrade)
    before = sheet_of(draft, PLAYER_ID, Sheet).credits.current

    assert _bought(engine, draft, "tachyon-burst", onto_id=ship)

    assert "tachyon-burst" in [item.id for item in draft.world.children(ship, "item")]
    assert sheet_of(draft, PLAYER_ID, Sheet).credits.current == before - RULES.ship_upgrade

    with pytest.raises(ValueError, match="name the ship"):
        _ = _bought(engine, draft, "jammer")
    with pytest.raises(ValueError, match="leave `onto_id` null"):
        _ = _bought(engine, draft, "pistol", onto_id=ship)


def test_duplicate_shop_ids_across_packs_are_refused(tmp_path: Path) -> None:
    srd = build(tmp_path).packs["srd"]
    (tmp_path / "duplicate.json").write_text(srd.model_dump_json())

    with pytest.raises(ValueError, match="duplicate 24XX gear ids"):
        _ = build(tmp_path)


def test_a_decision_this_engine_cannot_play_or_read_is_refused() -> None:
    engine, _ = game(TWENTYFOURXX)

    with pytest.raises(ValueError, match="cannot play a 'spend-momentum' decision"):
        engine.check_pending(
            PendingDecision(
                kind="spend-momentum",
                prompt="Spend a point?",
                options=(),
                allows_text=True,
                payload={},
            )
        )
    with pytest.raises(ValidationError):
        engine.check_pending(
            PendingDecision(
                kind="stake",
                prompt=RISK,
                options=(DecisionOption(id="proceed", label="Proceed"),),
                allows_text=True,
                payload={"goal": "an attempt with no actor"},
            )
        )


def test_creation_hands_over_the_kit_as_carried_items_and_lands_the_training_die() -> None:
    creation = ENGINES_BUILT[TWENTYFOURXX].creation
    picks: Picks = {
        "pack": "srd",
        "specialty": "psychic",
        "training": "telepathy-at-d10",
        "origin": "human",
        "skill-1": "stealth",
        "skill-2": "deception",
        "skill-3": "connections",
    }
    created = creation.create("Vex", "A quiet reader of rooms.", picks)
    assert [item.name for item in created.profile.items] == ["Comm", "Bottle of PsychOut"]
    assert created.profile.traits == ()
    assert created.rules["skills"] == {
        "Telepathy": 10,
        "Stealth": 8,
        "Deception": 8,
        "Connections": 8,
    }


def test_a_bulky_kit_item_carries_the_bulky_mark() -> None:
    creation = ENGINES_BUILT[TWENTYFOURXX].creation
    picks: Picks = {
        "pack": "srd",
        "specialty": "tech",
        "origin": "human",
        "skill-1": "climbing",
        "skill-2": "stealth",
        "skill-3": "tracking",
    }
    created = creation.create("Wren", "Solders anything.", picks)
    computer = next(item for item in created.profile.items if item.id == "custom-computer")
    assert computer.traits == [] and computer.rules == {"bulky": True}


def test_an_alien_invents_traits_the_menu_never_listed() -> None:
    creation = ENGINES_BUILT[TWENTYFOURXX].creation
    picks: Picks = {
        "pack": "srd",
        "specialty": "sneak",
        "origin": "alien",
        "trait-1": "Wings",
        "trait-2": "A tail that reads the air",
    }
    created = creation.create("Ixl", "Feathered and patient.", picks)
    names = [trait.name for trait in created.profile.traits]
    assert names == ["Wings", "A tail that reads the air"]


def test_a_humans_three_increases_can_stack_onto_one_skill() -> None:
    creation = ENGINES_BUILT[TWENTYFOURXX].creation
    picks: Picks = {
        "pack": "srd",
        "specialty": "sneak",
        "origin": "human",
        "skill-1": "tracking",
        "skill-2": "tracking",
        "skill-3": "tracking",
    }
    created = creation.create("Rho", "Never stops moving.", picks)
    assert created.rules["skills"] == {"Climbing": 8, "Stealth": 8, "Tracking": 12}
