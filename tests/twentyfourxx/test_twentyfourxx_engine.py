from random import Random

import pytest
from core_test_support import TWENTYFOURXX, at_boundary, capability, game
from pydantic import JsonValue, ValidationError

from aidm.engines.twentyfourxx.actions import (
    Attempt,
    ChangeCredits,
    CompleteJob,
    LuckTest,
    outcome_for,
    pool_faces,
    resolve_attempt,
    resolve_luck_test,
)
from aidm.engines.twentyfourxx.advance import Advance
from aidm.engines.twentyfourxx.mechanics import Mechanics, Sheet
from aidm.engines.twentyfourxx.rules import TwentyfourxxEngine
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.creation import Picks

MARA = EntityId("mara")


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
        actor_id=PLAYER_ID, goal="climb the wall", skill=skill, helped=helped, hindered=hindered
    )
    assert pool_faces(sheet, action, None) == expected


def test_a_helper_rolls_their_own_skill_die_into_the_pool() -> None:
    sheet = Sheet(skills={"Climbing": 10})
    helper = Sheet(skills={"Hacking": 12})
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="climb the wall",
        skill="Climbing",
        helper_id=MARA,
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

    unknown_skill = Attempt(actor_id=PLAYER_ID, goal="Kael picks the lock.", skill="Lockpicking")
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
        goal="Kael picks the lock while Mara covers the door.",
        helper_id=MARA,
        helper_skill="Lockpicking",
    )
    with pytest.raises(ValueError, match="helper_skill"):
        resolve_attempt(state.draft(), action, Random(0))


def test_naming_both_an_ally_and_a_helped_tag_is_refused_at_the_schema() -> None:
    with pytest.raises(ValidationError):
        Attempt(
            actor_id=PLAYER_ID,
            goal="Kael picks the lock.",
            helper_id=MARA,
            helped="a steady rope",
        )


def test_a_job_raises_one_skill_a_step_and_pays_rolled_credits() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = capability(engine)
    ready = at_boundary(state)
    (offer,) = advancement.offers(ready)
    before = ready.mechanics_as(Mechanics).sheets[PLAYER_ID]

    raise_existing = Advance(skill="Tracking", why="the climb taught them the route")
    draft = ready.draft()
    facts = advancement.resolve(draft, offer, raise_existing, Random(3))
    grown = draft.committed()

    sheet = grown.mechanics_as(Mechanics).sheets[PLAYER_ID]
    assert sheet.skills["Tracking"] == 10
    assert sheet.jobs.current == before.jobs.current + 1
    (dice_fact,) = [fact for fact in facts if fact.kind == "dice_rolled"]
    assert sheet.credits.current - before.credits.current == dice_fact.data["kept"]

    take_new = Advance(skill="Lockpicking", why="the job called for it")
    draft = ready.draft()
    advancement.resolve(draft, offer, take_new, Random(4))
    assert draft.committed().mechanics_as(Mechanics).sheets[PLAYER_ID].skills["Lockpicking"] == 8


def test_an_advance_is_offered_only_once_a_job_is_recorded() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = capability(engine)
    assert advancement.offers(state) == ()

    draft = state.draft()
    engine.apply(draft, CompleteJob())
    after = draft.committed()

    (offer,) = advancement.offers(after)
    assert offer.subject_id == PLAYER_ID


def test_a_skill_already_at_d12_is_refused_and_the_refusal_reaches_the_advisor() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = capability(engine)
    ready = at_boundary(state)

    draft = ready.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[PLAYER_ID].skills["Climbing"] = 12
    maxed = draft.committed()

    (offer,) = advancement.offers(maxed)
    capped = Advance(skill="Climbing", why="there is nowhere higher to climb")

    message = advancement.violation(maxed, offer, capped)
    assert message is not None
    assert "d12" in message


def test_credits_are_paid_charged_and_never_overdrawn() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    sheet = draft.mechanics_as(Mechanics).sheets[PLAYER_ID]
    before = sheet.credits.current

    paid = engine.apply_effect(draft, _credits(3))
    assert [fact.kind for fact in paid] == ["counter_changed"]
    assert sheet.credits.current == before + 3

    with pytest.raises(ValueError, match="cannot be spent"):
        _ = engine.apply_effect(draft, _credits(-(before + 4)))
    assert sheet.credits.current == before + 3

    with pytest.raises(ValidationError):
        _ = ChangeCredits(actor_id=PLAYER_ID, amount=0)


def _credits(amount: int) -> dict[str, JsonValue]:
    return {"name": "change-credits", "args": {"actor_id": PLAYER_ID, "amount": amount}}


def test_a_tested_bad_luck_risk_that_lands_leaves_a_note_for_the_next_turn() -> None:
    _, state = game(TWENTYFOURXX)
    action = Attempt(
        actor_id=PLAYER_ID, goal="Kael tries something risky.", luck_test="running out of oil"
    )

    draft = state.draft()
    facts = resolve_attempt(draft, action, Random(2)).facts
    (bad_luck_roll,) = [
        fact
        for fact in facts
        if fact.kind == "dice_rolled" and fact.data["reason"] == "bad luck — running out of oil"
    ]
    kept = bad_luck_roll.data["kept"]
    assert isinstance(kept, int)
    assert 1 <= kept <= 4
    assert len(draft.world.pending_notes) == 1
    assert any(fact.kind == "luck_tested" for fact in facts)

    draft = state.draft()
    facts = resolve_attempt(draft, action, Random(1)).facts
    assert draft.world.pending_notes == state.world.pending_notes == ()
    assert not any(fact.kind == "luck_tested" for fact in facts)


def test_bad_luck_that_bites_hands_the_turn_back_even_when_the_attempt_succeeded() -> None:
    _, state = game(TWENTYFOURXX)
    action = Attempt(
        actor_id=PLAYER_ID, goal="Kael tries something risky.", luck_test="running out of oil"
    )
    # Seed 6 succeeds and still lands trouble, so the yield can only come from the luck test.
    resolution = resolve_attempt(state.draft(), action, Random(6))

    assert resolution.outcome == "success"
    assert resolution.followup == "settle"


def test_a_standalone_luck_test_needs_no_attempt_and_only_trouble_hands_the_turn_back() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")

    draft = state.draft()
    trouble = resolve_luck_test(draft, action, Random(2))
    assert trouble.outcome == "trouble"
    assert trouble.followup == "settle"
    assert len(draft.world.pending_notes) == 1

    signs = resolve_luck_test(state.draft(), action, Random(0))
    assert signs.outcome == "signs"
    assert signs.followup == "continue"

    draft = state.draft()
    clear = resolve_luck_test(draft, action, Random(5))
    assert clear.outcome == "clear"
    assert clear.followup == "continue"
    assert draft.world.pending_notes == ()


def test_creation_hands_over_the_kit_as_carried_items_and_lands_the_training_die() -> None:
    creation = TwentyfourxxEngine().creation
    assert creation is not None
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("psychic",),
        "training": ("telepathy-at-d10",),
        "origin": ("human",),
        "skills": ("stealth", "deception", "connections"),
    }
    created = creation.create("Vex", "A quiet reader of rooms.", picks)
    assert [item.name for item in created.profile.items] == ["Comm", "Bottle of PsychOut"]
    assert created.profile.traits == ()
    assert created.overlay.character["skills"] == {
        "Telepathy": 10,
        "Stealth": 8,
        "Deception": 8,
        "Connections": 8,
    }


def test_a_bulky_kit_item_carries_the_bulky_trait() -> None:
    creation = TwentyfourxxEngine().creation
    assert creation is not None
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("tech",),
        "origin": ("human",),
        "skills": ("climbing", "stealth", "tracking"),
    }
    created = creation.create("Wren", "Solders anything.", picks)
    computer = next(item for item in created.profile.items if item.id == "custom-computer")
    assert [trait.id for trait in computer.traits] == ["bulky"]


def test_an_alien_invents_traits_the_menu_never_listed() -> None:
    creation = TwentyfourxxEngine().creation
    assert creation is not None
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("sneak",),
        "origin": ("alien",),
        "traits": ("Wings", "A tail that reads the air"),
    }
    created = creation.create("Ixl", "Feathered and patient.", picks)
    names = [trait.name for trait in created.profile.traits]
    assert names == ["Wings", "A tail that reads the air"]


def test_a_humans_three_increases_can_stack_onto_one_skill() -> None:
    creation = TwentyfourxxEngine().creation
    assert creation is not None
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("sneak",),
        "origin": ("human",),
        "skills": ("tracking", "tracking", "tracking"),
    }
    created = creation.create("Rho", "Never stops moving.", picks)
    assert created.overlay.character["skills"] == {"Climbing": 8, "Stealth": 8, "Tracking": 12}
