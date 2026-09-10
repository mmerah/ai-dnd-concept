from random import Random

import pytest
from support.game import ENGINE, initialized, loner_sheet
from support.table import change, updated

from aidm.core.entities import Refusal
from aidm.core.facts import cards
from aidm.core.io import decode
from aidm.core.play import PendingDecision
from aidm.engines.base import PLAYER_ID, Counter
from aidm.engines.loner3e.tools import Question, defeat_note, outcome_for, twist_note, twist_pairing
from aidm.engines.loner3e.world import LUCK_MAX, TIES_PER_TWIST
from aidm.engines.scenes.packs import SRD_PACK

FOE = "mara"
MAP = "vault-map"


def _seal(**args: object) -> Question:
    return Question.model_validate(
        {
            "what": "Force the seal",
            "actor_id": PLAYER_ID,
            "question": "Does he get the seal open before the whispering finds him?",
        }
        | args
    )


def _duel() -> Question:
    return Question(
        what="Force her back from the door",
        actor_id=PLAYER_ID,
        question="Does he force her back from the door?",
        opponent_id=FOE,
    )


def test_the_outcome_ladder_covers_every_pair_of_dice() -> None:
    tally: dict[str, int] = {}
    for chance in range(1, 7):
        for risk in range(1, 7):
            outcome = outcome_for(chance, risk)
            tally[outcome.name] = tally.get(outcome.name, 0) + 1
    assert tally == {
        "yes-and": 3,
        "yes": 9,
        "yes-but": 9,
        "no-but": 3,
        "no": 9,
        "no-and": 3,
    }


def test_the_twist_table_reads_a_subject_off_one_die_and_an_action_off_the_other() -> None:
    twists = ENGINE.twist_table()
    assert len(twists) == 6
    assert twist_pairing(4, 2, twists) == ("A physical event", "Alters the location")
    assert "A PHYSICAL EVENT / ALTERS THE LOCATION" in twist_note(*twist_pairing(4, 2, twists))


def test_a_question_puts_two_dice_to_the_answer_and_costs_no_luck_on_its_own() -> None:
    _, state = initialized()
    draft = state.draft()

    _ = ENGINE.roll(draft, _seal(), Random(17))

    assert loner_sheet(draft, PLAYER_ID).luck.current == LUCK_MAX


def test_the_question_is_the_masters_memory_and_never_reaches_the_narrator() -> None:
    """The master writes the question and may name unrevealed canon in it, even on a no."""
    _, state = initialized()
    question = _seal()

    facts = ENGINE.roll(state.draft(), question, Random(17))

    asked = next(fact for fact in facts if fact.trace.startswith("asked:"))
    answered = next(fact for fact in facts if fact.dice)
    assert not asked.told
    assert question.question in asked.trace
    assert answered.told
    assert question.question not in answered.trace
    assert answered.trace.startswith(f"{question.what} — oracle, neutral: ")
    assert answered.card.startswith(answered.trace)


def test_a_question_the_fiction_cannot_carry_is_refused_with_the_reason() -> None:
    _, state = initialized()

    elsewhere = _seal(opponent_id="cloister-rat")
    with pytest.raises(Refusal, match="is not here with the player"):
        _ = ENGINE.roll(state.draft(), elsewhere, Random(0))
    with pytest.raises(Refusal, match="their own opposition"):
        _ = ENGINE.roll(state.draft(), _seal(opponent_id=PLAYER_ID), Random(0))


def test_the_judged_position_is_what_reaches_the_dice_and_the_record() -> None:
    _, state = initialized()
    action = Question(
        what="Force the seal",
        actor_id=PLAYER_ID,
        question="Does he force the seal before the whispering finds him?",
        position="disadvantage",
        edge="Never Walks Away",
    )

    facts = ENGINE.roll(state.draft(), action, Random(1))

    (oracle,) = cards(facts)
    assert oracle.card.startswith("Force the seal — oracle, disadvantage (Never Walks Away): ")
    assert oracle.dice[1].faces == (6, 6)


def test_a_tie_ticks_the_twist_and_the_third_tie_calls_one() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.twist.current = TIES_PER_TWIST - 1
    primed = draft.commit()

    action = Question(what="Slip past", actor_id=PLAYER_ID, question="Does he slip past unheard?")
    draft = primed.draft()
    # Seed 0 rolls chance 4 against risk 4: the tie that ticks the twist over.
    facts = ENGINE.roll(draft, action, Random(0))

    _, twist = cards(facts)
    subject, action_name = twist.card.removeprefix("Twist — ").split(" / ")
    rolled = twist_note(subject, action_name)
    assert draft.payload.twist.current == 0
    assert rolled in draft.notes


def test_a_tie_ticks_the_twist_only_outside_a_conflict() -> None:
    _, state = initialized()

    # Seed 0 rolls chance 4 against risk 4: a tie, in and out of a conflict.
    duel_draft = state.draft()
    facts = ENGINE.roll(duel_draft, _duel(), Random(0))
    (oracle, *_) = cards(facts)
    assert max(oracle.dice[0].rolled) == max(oracle.dice[1].rolled)
    assert duel_draft.payload.twist.current == 0

    solo_draft = state.draft()
    _ = ENGINE.roll(solo_draft, _seal(), Random(0))
    assert solo_draft.payload.twist.current == 1


def test_a_conflict_exchange_moves_luck_off_whichever_side_lost_it() -> None:
    _, state = initialized()
    # Every answer the ladder can give costs somebody luck in a conflict.
    ladder = [outcome_for(chance, risk) for chance in range(1, 7) for risk in range(1, 7)]
    assert all(outcome.harm != 0 for outcome in ladder)

    # Seed 0 rolls a 4-4 tie, a yes-but that costs the foe; seed 1 rolls 2 against 5, a no.
    for seed in (0, 1):
        draft = state.draft()
        facts = ENGINE.roll(draft, _duel(), Random(seed))
        (oracle,) = cards(facts)
        harm = outcome_for(max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)).harm
        loser, unharmed = (FOE, PLAYER_ID) if harm > 0 else (PLAYER_ID, FOE)
        assert loner_sheet(draft, loser).luck.current == LUCK_MAX - abs(harm)
        assert loner_sheet(draft, unharmed).luck.current == LUCK_MAX
        # SRD: the Twist Counter does not apply to Harm & Luck, so a conflict tie never ticks it.
        assert draft.payload.twist.current == 0


def test_luck_running_out_ends_the_conflict_and_resets_both_pools() -> None:
    _, state = initialized()
    draft = state.draft()
    # A 10-max pool proves the reset lands on the sheet's own maximum, not on a +luck_max delta.
    loner_sheet(draft, FOE).luck = Counter(current=1, maximum=10)
    hurt = draft.commit()

    draft = hurt.draft()
    # Seed 0 rolls chance 4 against risk 4: a yes-but, one luck off the foe's last point.
    _ = ENGINE.roll(draft, _duel(), Random(0))

    assert loner_sheet(draft, FOE).luck.current == 10
    assert loner_sheet(draft, PLAYER_ID).luck.current == LUCK_MAX
    assert defeat_note(draft.payload.require(FOE).name) in draft.notes
    # The conflict is over, so the defeat note steers the same run instead of handing control back.
    assert draft.pending is None


def test_an_exchange_both_sides_survive_hands_the_next_key_action_to_the_player() -> None:
    _, state = initialized()
    draft = state.draft()

    _ = ENGINE.roll(draft, _duel(), Random(0))

    decision = draft.pending
    assert decision is not None
    foe = draft.payload.require(FOE)
    expected = draft.payload.conflict_prompt(draft.payload.player, foe)
    assert (decision.kind, decision.prompt) == ("conflict", expected)
    assert foe.name in decision.prompt
    assert decision.options == ()


def test_a_thing_fights_back_with_a_sheet_of_its_own_when_it_is_here() -> None:
    _, state = initialized()

    # The map is hidden in this scene, so nothing can be rolled against it yet.
    with pytest.raises(Refusal, match="is not here with the player"):
        _ = ENGINE.roll(state.draft(), _seal(opponent_id=MAP), Random(0))

    draft = state.draft()
    _ = change(ENGINE, draft, "reveal", entity_id=MAP)
    _ = ENGINE.roll(draft, _seal(opponent_id=MAP), Random(0))

    resisted = draft.payload.require(MAP).luck.current
    assert min(resisted, loner_sheet(draft, PLAYER_ID).luck.current) < LUCK_MAX


def test_the_open_ended_hand_back_survives_a_save() -> None:
    engine, state = initialized()
    hand_back = PendingDecision(
        kind="conflict", prompt="Say your next key action.", options=(), allows_text=True
    )
    draft = state.draft()
    draft.pending = hand_back

    assert engine.restore(decode(draft.commit().model_dump_json())).pending == hand_back


def test_an_actor_already_at_zero_luck_refuses_another_exchange() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, FOE).luck.current = 0
    spent = draft.commit()

    with pytest.raises(Refusal, match="already out of luck"):
        _ = ENGINE.roll(spent.draft(), _duel(), Random(0))


def test_restoring_luck_that_is_already_full_is_a_quiet_no_op() -> None:
    _, state = initialized()

    assert change(ENGINE, state.draft(), "restore_luck", entity_id=PLAYER_ID) == []


def test_a_game_records_its_table_sets_and_is_refused_without_them() -> None:
    engine, state = initialized()
    assert state.packs == (SRD_PACK,)

    stranded = updated(state, packs=(SRD_PACK, "uninstalled"))

    with pytest.raises(Refusal, match="not installed"):
        engine.validate(stranded)
