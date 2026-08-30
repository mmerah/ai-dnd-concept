from random import Random

from core_test_support import TWENTYFOURXX, game

from aidm.engines.twentyfourxx.rules import (
    Attempt,
    LuckTest,
    apply_change_credits,
    outcome_for,
    resolve_attempt,
    resolve_luck_test,
)
from aidm.state.entities import PLAYER_ID
from aidm.state.facts import cards

GOAL = "Kael scales the crumbling wall"


def _climb(**args: object) -> Attempt:
    base = {
        "actor_id": PLAYER_ID,
        "goal": GOAL,
        "risk": "a fall onto the rubble below",
        "skill": "Climbing",
        "hit": True,
    }
    return Attempt.model_validate(base | args)


def test_the_attempt_card_carries_the_dice_that_were_rolled() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(), Random(0))
    (rolled,) = [fact for fact in facts if fact.kind == "dice_rolled"]

    (event,) = cards(facts)
    (die,) = event.dice
    shown = ", ".join(str(value) for value in die.rolled)
    assert rolled.trace.endswith(f"[{shown}]")
    assert event.card.startswith("Attempt — ")


def test_the_attempt_card_names_the_skill_used() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(), Random(0))

    (event,) = cards(facts)
    assert "Skill Climbing" in event.card


def test_a_circumstance_help_adds_a_bare_d6() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(helped="a steady rope"), Random(0))

    (event,) = cards(facts)
    assert "Help d6" in event.card


def test_the_outcome_ladder_is_mapped_onto_the_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(), Random(0))

    (event,) = cards(facts)
    assert event.card.startswith(f"Attempt — {outcome_for(max(event.dice[0].rolled))}")


def test_the_luck_test_card_carries_its_die_and_the_trouble_label() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")
    facts = resolve_luck_test(state.draft(), action, Random(2))

    (event,) = cards(facts)
    assert event.card == "Luck Test — Trouble"
    assert len(event.dice) == 1
    assert len(event.dice[0].rolled) == 1


def test_a_clear_luck_test_shows_no_card() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")
    facts = resolve_luck_test(state.draft(), action, Random(5))

    assert cards(facts) == ()


def test_a_luck_test_attached_to_an_attempt_adds_a_luck_dice_group() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(luck_test="a rope frays"), Random(0))

    (event,) = cards(facts)
    assert [die.label for die in event.dice] == ["Pool", "Luck"]
    assert event.card.split("\n")[-1] == "bad luck — a rope frays: signs of it"


def test_a_clear_luck_test_attached_to_an_attempt_still_adds_a_luck_dice_group() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(luck_test="a rope frays"), Random(1))

    (event,) = cards(facts)
    assert [die.label for die in event.dice] == ["Pool", "Luck"]
    assert "bad luck" not in event.card


def test_a_hindered_attempt_says_so_on_the_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(hindered="loose scree"), Random(0))

    (event,) = cards(facts)
    assert "Hindered" in event.card


def test_paying_credits_shows_as_a_counter_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = tuple(apply_change_credits(state.draft(), PLAYER_ID, 3))

    (event,) = cards(facts)
    assert event.card == "Credits +3 -> 5"


def test_charging_credits_shows_as_a_counter_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = tuple(apply_change_credits(state.draft(), PLAYER_ID, -1))

    (event,) = cards(facts)
    assert event.card == "Credits -1 -> 1"
