from random import Random

from support.game import ENGINE, initialized, loner_sheet
from support.table import change

from aidm.core.entities import EntityId
from aidm.core.facts import cards
from aidm.engines.base import PLAYER_ID
from aidm.engines.loner3e.tools import Question, outcome_for
from aidm.engines.loner3e.world import TIES_PER_TWIST

FOE = EntityId("mara")


def _seal(**args: object) -> Question:
    return Question.model_validate(
        {
            "what": "Force the seal",
            "actor_id": PLAYER_ID,
            "question": "Does he get the seal open before the whispering finds him?",
        }
        | args
    )


def test_a_neutral_question_shows_one_chance_die_and_one_risk_die() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(), Random(0))

    (oracle,) = cards(facts)
    assert [die.label for die in oracle.dice] == ["Chance", "Risk"]
    assert len(oracle.dice[0].rolled) == 1
    assert len(oracle.dice[1].rolled) == 1
    assert oracle.card.startswith("Force the seal — oracle, neutral: ")


def test_advantage_rolls_two_chance_dice() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(position="advantage", edge="Relic Hunter"), Random(0))

    (oracle,) = cards(facts)
    assert len(oracle.dice[0].rolled) == 2
    assert len(oracle.dice[1].rolled) == 1
    assert oracle.card.startswith("Force the seal — oracle, advantage (Relic Hunter): ")
    assert oracle.trace == oracle.card


def test_disadvantage_rolls_two_risk_dice() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(position="disadvantage"), Random(0))

    (oracle,) = cards(facts)
    assert len(oracle.dice[0].rolled) == 1
    assert len(oracle.dice[1].rolled) == 2


def test_the_six_way_outcome_is_mapped_onto_the_card() -> None:
    _, state = initialized()
    facts = ENGINE.roll(state.draft(), _seal(), Random(0))

    (oracle,) = cards(facts)
    chance, risk = max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)
    assert oracle.card.endswith(f": {outcome_for(chance, risk).wording}")


def test_a_defeat_shows_the_owner_prefixed_effects_in_fact_order() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, FOE).luck.current = 1
    weakened = draft.commit()
    duel = Question(
        what="Force her back",
        actor_id=PLAYER_ID,
        question="Does he force her back from the door?",
        opponent_id=FOE,
    )

    # Seed 0 rolls chance 4 against risk 4: a yes-but, one luck off the foe's last point.
    facts = ENGINE.roll(weakened.draft(), duel, Random(0))
    (oracle,) = cards(facts)

    assert oracle.card.split("\n")[1:] == [
        "Mara: Luck -1 -> 0/6",
        "Mara is out of luck",
        "Mara: Luck +6 -> 6/6",
    ]


def test_a_twist_card_lands_only_once_a_twist_fires() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.twist.current = TIES_PER_TWIST - 1
    primed = draft.commit()

    # Seed 0 rolls chance 4 against risk 4: the tie that ticks the twist over.
    facts = ENGINE.roll(primed.draft(), _seal(), Random(0))

    oracle, twist = cards(facts)
    assert oracle.card.startswith("Force the seal — oracle, ")
    subject, action = twist.card.removeprefix("Twist — ").split(" / ")
    assert subject and action
    (twist_dice,) = twist.dice
    assert twist_dice.faces == (6, 6)


def test_restoring_luck_shows_as_a_counter_card() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, PLAYER_ID).luck.current = 1
    spent = draft.commit()

    facts = tuple(change(ENGINE, spent.draft(), "restore_luck", entity_id=PLAYER_ID))
    (event,) = cards(facts)
    assert event.card == "Luck +5 -> 6/6"
