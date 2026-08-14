from random import Random

import pytest
from core_test_support import TWENTYFOURXX, capability, game
from loner3e_test_support import at_milestone

from aidm.engines.twentyfourxx.actions import Attempt, outcome_for, pool_faces, resolve_attempt
from aidm.engines.twentyfourxx.advance import Advance
from aidm.engines.twentyfourxx.mechanics import Mechanics, Sheet
from aidm.engines.twentyfourxx.rules import TwentyfourxxEngine
from aidm.state.base import PLAYER_ID
from aidm.state.creation import Picks


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
    assert pool_faces(sheet, action) == expected


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


def test_an_attempt_is_refused_before_it_rolls_when_the_plan_invents_something() -> None:
    _, state = game(TWENTYFOURXX)

    unknown_skill = Attempt(actor_id=PLAYER_ID, goal="Kael picks the lock.", skill="Lockpicking")
    with pytest.raises(ValueError) as skill_error:
        resolve_attempt(state.draft(), unknown_skill, Random(0))
    message = str(skill_error.value)
    assert "Climbing" in message
    assert "Stealth" in message
    assert "Tracking" in message

    unknown_tag = Attempt(actor_id=PLAYER_ID, goal="Kael calls in a favor.", helped="Silver Tongue")
    with pytest.raises(ValueError, match="tagged"):
        resolve_attempt(state.draft(), unknown_tag, Random(0))


def test_a_job_raises_one_skill_a_step_and_pays_rolled_credits() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = capability(engine)
    ready = at_milestone(state)
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


def test_a_skill_already_at_d12_is_refused_and_the_refusal_reaches_the_advisor() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = capability(engine)
    ready = at_milestone(state)

    draft = ready.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[PLAYER_ID].skills["Climbing"] = 12
    maxed = draft.committed()

    (offer,) = advancement.offers(maxed)
    capped = Advance(skill="Climbing", why="there is nowhere higher to climb")

    message = advancement.violation(maxed, offer, capped)
    assert message is not None
    assert "d12" in message


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
    assert resolution.flow == "yield-to-player"


def test_creation_vendors_the_kit_as_traits_and_lands_the_training_die() -> None:
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
    assert [trait.name for trait in created.profile.traits] == ["Comm", "Bottle of PsychOut"]
    assert created.overlay.character["skills"] == {
        "Telepathy": 10,
        "Stealth": 8,
        "Deception": 8,
        "Connections": 8,
    }


def test_an_alien_picks_its_two_traits_from_the_menu() -> None:
    creation = TwentyfourxxEngine().creation
    assert creation is not None
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("sneak",),
        "origin": ("alien",),
        "traits": ("wings", "natural-camouflage"),
    }
    created = creation.create("Ixl", "Feathered and patient.", picks)
    names = [trait.name for trait in created.profile.traits]
    assert names == [
        "Comm",
        "Climbing Gear",
        "Night Vision Goggles",
        "Wings",
        "Natural Camouflage",
    ]
