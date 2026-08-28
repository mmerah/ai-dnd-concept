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
from aidm.state.facts import EventBadge, player_events

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


def test_the_pool_faces_rolls_and_kept_are_preserved_on_the_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(), Random(0))
    (rolled,) = [fact for fact in facts if fact.kind == "dice_rolled"]

    (event,) = player_events(facts)
    (die,) = event.dice
    shown = ", ".join(str(value) for value in die.rolled)
    assert rolled.trace.endswith(f"[{shown}] -> {die.kept}")
    assert event.title == "Attempt"


def test_the_skill_badge_names_the_skill_used() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(), Random(0))

    (event,) = player_events(facts)
    assert event.badges == (EventBadge(label="Skill", value="Climbing"),)


def test_a_circumstance_help_adds_a_bare_d6() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(helped="a steady rope"), Random(0))

    (event,) = player_events(facts)
    assert EventBadge(label="Help", value="d6") in event.badges


def test_the_outcome_ladder_is_mapped_onto_the_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(), Random(0))

    (event,) = player_events(facts)
    assert event.outcome == outcome_for(event.dice[0].kept)


def test_the_luck_test_card_carries_its_die_and_the_trouble_label() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")
    facts = resolve_luck_test(state.draft(), action, Random(2))

    (event,) = player_events(facts)
    assert event.title == "Luck Test"
    assert event.outcome == "Trouble"
    assert len(event.dice) == 1
    assert len(event.dice[0].rolled) == 1


def test_a_clear_luck_test_shows_no_card() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")
    facts = resolve_luck_test(state.draft(), action, Random(5))

    assert player_events(facts) == ()


def test_a_luck_test_attached_to_an_attempt_adds_a_luck_dice_group() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(luck_test="a rope frays"), Random(0))

    (event,) = player_events(facts)
    assert [die.label for die in event.dice] == ["Pool", "Luck"]
    assert len(event.effects) == 1
    assert event.effects[0] == "bad luck — a rope frays: signs of it"


def test_a_clear_luck_test_attached_to_an_attempt_still_adds_a_luck_dice_group() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(luck_test="a rope frays"), Random(1))

    (event,) = player_events(facts)
    assert [die.label for die in event.dice] == ["Pool", "Luck"]
    assert event.effects == ()


def test_a_hindered_attempt_badges_hindered() -> None:
    _, state = game(TWENTYFOURXX)
    facts = resolve_attempt(state.draft(), _climb(hindered="loose scree"), Random(0))

    (event,) = player_events(facts)
    assert EventBadge(label="Hindered", value="") in event.badges


def test_paying_credits_shows_as_a_counter_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = tuple(apply_change_credits(state.draft(), PLAYER_ID, 3))

    (event,) = player_events(facts)
    assert event.title == "Credits +3 -> 5"
    assert event.icon == "payments"


def test_charging_credits_shows_as_a_counter_card() -> None:
    _, state = game(TWENTYFOURXX)
    facts = tuple(apply_change_credits(state.draft(), PLAYER_ID, -1))

    (event,) = player_events(facts)
    assert event.title == "Credits -1 -> 1"
    assert event.icon == "payments"
