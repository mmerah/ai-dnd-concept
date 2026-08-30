from random import Random

from core_test_support import initialized, loner_sheet
from loner3e_test_support import TWISTS

from aidm.engines.loner3e.rules import (
    Question,
    apply_restore_luck,
    outcome_for,
    resolve_question,
)
from aidm.engines.loner3e.state import TIES_PER_TWIST
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import cards

FOE = EntityId("mara")


def _seal(**args: object) -> Question:
    return Question.model_validate(
        {
            "actor_id": PLAYER_ID,
            "question": "Does he get the seal open before the whispering finds him?",
        }
        | args
    )


def test_a_neutral_question_shows_one_chance_die_and_one_risk_die() -> None:
    _, state = initialized()
    facts = resolve_question(state.draft(), _seal(), Random(0), TWISTS)

    (oracle,) = cards(facts)
    assert [die.label for die in oracle.dice] == ["Chance", "Risk"]
    assert len(oracle.dice[0].rolled) == 1
    assert len(oracle.dice[1].rolled) == 1
    assert oracle.card.startswith("Oracle — Neutral → ")


def test_advantage_rolls_two_chance_dice() -> None:
    _, state = initialized()
    facts = resolve_question(
        state.draft(), _seal(position="advantage", edge="Relic Hunter"), Random(0), TWISTS
    )

    (oracle,) = cards(facts)
    assert len(oracle.dice[0].rolled) == 2
    assert len(oracle.dice[1].rolled) == 1
    assert oracle.card.startswith("Oracle — Advantage (Relic Hunter) → ")


def test_disadvantage_rolls_two_risk_dice() -> None:
    _, state = initialized()
    facts = resolve_question(state.draft(), _seal(position="disadvantage"), Random(0), TWISTS)

    (oracle,) = cards(facts)
    assert len(oracle.dice[0].rolled) == 1
    assert len(oracle.dice[1].rolled) == 2


def test_the_six_way_outcome_is_mapped_onto_the_card() -> None:
    _, state = initialized()
    facts = resolve_question(state.draft(), _seal(), Random(0), TWISTS)

    (oracle,) = cards(facts)
    chance, risk = max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)
    assert oracle.card.endswith(f"→ {outcome_for(chance, risk).name}")


def test_a_defeat_shows_the_owner_prefixed_effects_in_fact_order() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, FOE).luck.current = 1
    weakened = draft.committed()
    duel = Question(
        actor_id=PLAYER_ID, question="Does he force her back from the door?", opponent_id=FOE
    )

    for seed in range(200):
        facts = resolve_question(weakened.draft(), duel, Random(seed), TWISTS)
        (oracle,) = cards(facts)
        if outcome_for(max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)).harm > 0:
            break
    else:
        raise AssertionError("no seed under 200 dealt the opponent harm")

    assert oracle.card.split("\n")[1:] == [
        "Mara: Luck -1 -> 0/6",
        "Mara is out of luck",
        "Mara: Luck +6 -> 6/6",
    ]


def test_a_twist_card_lands_only_once_a_twist_fires() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.twist.current = TIES_PER_TWIST - 1
    primed = draft.committed()

    for seed in range(200):
        facts = resolve_question(primed.draft(), _seal(), Random(seed), TWISTS)
        landed = cards(facts)
        if len(landed) == 2:
            break
    else:
        raise AssertionError("no seed under 200 tied the dice")

    oracle, twist = landed
    assert oracle.card.startswith("Oracle — ")
    subject, action = twist.card.removeprefix("Twist — ").split(" / ")
    assert subject and action
    assert len(twist.dice) == 2
    assert all(len(die.rolled) == 1 for die in twist.dice)


def test_restoring_luck_shows_as_a_counter_card() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1
    spent = draft.committed()

    facts = tuple(apply_restore_luck(spent.draft(), PLAYER_ID))
    (event,) = cards(facts)
    assert event.card == "Luck +5 -> 6/6"
