from random import Random

import pytest
from core_test_support import initialized, loner_sheet, updated
from loner3e_test_support import ENGINE, hub_world

from aidm.core.entities import EntityId
from aidm.core.facts import cards
from aidm.core.play import PendingDecision
from aidm.engines.base import PLAYER_ID, Counter
from aidm.engines.hub import JOB_DONE, Offer
from aidm.engines.loner3e.tools import (
    Question,
    RestoreLuck,
    conflict_prompt,
    defeat_note,
    outcome_for,
    twist_note,
    twist_pairing,
)
from aidm.engines.loner3e.world import LUCK_MAX, TIES_PER_TWIST
from aidm.engines.scenes.tools import NextScene, Reveal

FOE = EntityId("mara")
MAP = EntityId("vault-map")


def _seal(**args: object) -> Question:
    return Question.model_validate(
        {
            "actor_id": PLAYER_ID,
            "question": "Does he get the seal open before the whispering finds him?",
        }
        | args
    )


def _duel() -> Question:
    return Question(
        actor_id=PLAYER_ID, question="Does he force her back from the door?", opponent_id=FOE
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

    facts = ENGINE.resolve_question(draft, _seal(), Random(17))

    assert [fact.kind for fact in facts] == ["dice_rolled", "dice_rolled", "question_answered"]
    assert loner_sheet(draft, PLAYER_ID).luck.current == LUCK_MAX


def test_a_question_the_fiction_cannot_carry_is_refused_with_the_reason() -> None:
    _, state = initialized()

    elsewhere = _seal(opponent_id="cloister-rat")
    with pytest.raises(ValueError, match="is not here with the player"):
        _ = ENGINE.resolve_question(state.draft(), elsewhere, Random(0))
    with pytest.raises(ValueError, match="their own opposition"):
        _ = ENGINE.resolve_question(state.draft(), _seal(opponent_id=PLAYER_ID), Random(0))


def test_the_judged_position_is_what_reaches_the_dice_and_the_record() -> None:
    _, state = initialized()
    action = Question(
        actor_id=PLAYER_ID,
        question="Does he force the seal before the whispering finds him?",
        position="disadvantage",
        edge="Never Walks Away",
    )

    facts = ENGINE.resolve_question(state.draft(), action, Random(1))

    (oracle,) = cards(facts)
    assert oracle.card.startswith("Oracle — Disadvantage (Never Walks Away) → ")
    assert oracle.dice[1].faces == (6, 6)


def test_a_tie_ticks_the_twist_and_the_third_tie_calls_one() -> None:
    _, state = initialized()
    draft = state.draft()
    draft.payload.twist.current = TIES_PER_TWIST - 1
    primed = draft.commit()

    action = Question(actor_id=PLAYER_ID, question="Does he slip past unheard?")
    for seed in range(200):
        draft = primed.draft()
        facts = ENGINE.resolve_question(draft, action, Random(seed))
        if any(fact.kind == "twist_due" for fact in facts):
            break
    else:
        raise AssertionError("no seed under 200 tied the dice")

    _, twist = cards(facts)
    subject, action_name = twist.card.removeprefix("Twist — ").split(" / ")
    rolled = twist_note(subject, action_name)
    assert draft.payload.twist.current == 0
    assert rolled in draft.notes


def test_a_tie_ticks_the_twist_only_outside_a_conflict() -> None:
    _, state = initialized()

    for seed in range(200):
        duel_draft = state.draft()
        facts = ENGINE.resolve_question(duel_draft, _duel(), Random(seed))
        (oracle,) = cards(facts)
        if max(oracle.dice[0].rolled) == max(oracle.dice[1].rolled):
            break
    else:
        raise AssertionError("no seed under 200 tied the dice")
    assert duel_draft.payload.twist.current == 0

    solo_draft = state.draft()
    _ = ENGINE.resolve_question(solo_draft, _seal(), Random(seed))
    assert solo_draft.payload.twist.current == 1


def test_a_conflict_exchange_moves_luck_off_whichever_side_lost_it() -> None:
    _, state = initialized()
    # Every answer the ladder can give costs somebody luck in a conflict.
    ladder = [outcome_for(chance, risk) for chance in range(1, 7) for risk in range(1, 7)]
    assert all(outcome.harm != 0 for outcome in ladder)
    assert {outcome.name for outcome in ladder} == {
        "yes-and",
        "yes",
        "yes-but",
        "no-but",
        "no",
        "no-and",
    }

    for seed in range(200):
        draft = state.draft()
        facts = ENGINE.resolve_question(draft, _duel(), Random(seed))
        (oracle,) = cards(facts)
        harm = outcome_for(max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)).harm
        loser, held = (FOE, PLAYER_ID) if harm > 0 else (PLAYER_ID, FOE)
        assert loner_sheet(draft, loser).luck.current == LUCK_MAX - abs(harm)
        assert loner_sheet(draft, held).luck.current == LUCK_MAX
        # SRD: the Twist Counter does not apply to Harm & Luck, so a conflict tie never ticks it.
        assert not any(fact.kind == "twist_due" for fact in facts)
        assert draft.payload.twist.current == 0


def test_luck_running_out_ends_the_conflict_and_resets_both_pools() -> None:
    _, state = initialized()
    draft = state.draft()
    # A 10-max pool proves the reset lands on the sheet's own maximum, not on a +luck_max delta.
    loner_sheet(draft, FOE).luck = Counter(current=1, maximum=10)
    hurt = draft.commit()

    for seed in range(200):
        draft = hurt.draft()
        facts = ENGINE.resolve_question(draft, _duel(), Random(seed))
        (oracle,) = cards(facts)
        if outcome_for(max(oracle.dice[0].rolled), max(oracle.dice[1].rolled)).harm > 0:
            break
    else:
        raise AssertionError("no seed under 200 answered yes")

    assert loner_sheet(draft, FOE).luck.current == 10
    assert loner_sheet(draft, PLAYER_ID).luck.current == LUCK_MAX
    assert any(fact.kind == "conflict_lost" for fact in facts)
    assert defeat_note(draft.payload.require(FOE).name) in draft.notes
    # The conflict is over, so the defeat note steers the same run instead of handing control back.
    assert draft.pending is None


def test_an_exchange_both_sides_survive_hands_the_next_key_action_to_the_player() -> None:
    _, state = initialized()
    draft = state.draft()

    _ = ENGINE.resolve_question(draft, _duel(), Random(0))

    decision = draft.pending
    assert decision is not None
    foe = draft.payload.require(FOE)
    expected = conflict_prompt(draft.payload, draft.payload.player, foe)
    assert (decision.kind, decision.prompt) == ("conflict", expected)
    assert foe.name in decision.prompt
    assert decision.options == ()


def test_a_thing_fights_back_with_a_sheet_of_its_own_when_it_is_here() -> None:
    _, state = initialized()

    # The map is hidden in this scene, so nothing can be rolled against it yet.
    with pytest.raises(ValueError, match="is not here with the player"):
        _ = ENGINE.resolve_question(state.draft(), _seal(opponent_id=MAP), Random(0))

    draft = state.draft()
    _ = ENGINE.apply_change(draft.payload, Reveal(verb="reveal", entity_id=MAP))
    facts = ENGINE.resolve_question(draft, _seal(opponent_id=MAP), Random(0))

    assert any(fact.kind == "question_answered" for fact in facts)
    resisted = draft.payload.require(MAP).luck.current
    assert min(resisted, loner_sheet(draft, PLAYER_ID).luck.current) < LUCK_MAX


def test_the_open_ended_hand_back_survives_a_save() -> None:
    engine, state = initialized()
    hand_back = PendingDecision(
        kind="conflict", prompt="Say your next key action.", options=(), allows_text=True
    )
    draft = state.draft()
    draft.pending = hand_back

    assert engine.restore(draft.commit().model_dump_json()).pending == hand_back


def test_an_actor_already_at_zero_luck_refuses_another_exchange() -> None:
    _, state = initialized()
    draft = state.draft()
    loner_sheet(draft, FOE).luck.current = 0
    spent = draft.commit()

    with pytest.raises(ValueError, match="already out of luck"):
        _ = ENGINE.resolve_question(spent.draft(), _duel(), Random(0))


def test_restoring_luck_that_is_already_full_is_a_quiet_no_op() -> None:
    _, state = initialized()

    assert ENGINE.restore_luck(state.draft(), RestoreLuck(actor_id=PLAYER_ID), Random(0)) == []


def test_next_scene_with_job_done_settles_the_job_and_is_refused_at_the_hub() -> None:
    draft = hub_world()
    world = draft.payload
    facts = ENGINE.next_scene(draft, NextScene(job_done=True), Random(0))
    assert world.run.left is not None
    assert world.jobs[-1].finished
    assert JOB_DONE in facts

    at_hub = hub_world()
    at_hub.payload.runs = [at_hub.payload.runs[0]]
    with pytest.raises(ValueError, match="no job is open here"):
        _ = ENGINE.next_scene(at_hub, NextScene(job_done=True), Random(0))


def test_check_game_refuses_a_campaign_meta_with_no_hub() -> None:
    engine, state = initialized()
    campaign_meta = state.scenario.model_copy(update={"kind": "campaign"})
    with pytest.raises(ValueError, match="campaign"):
        engine.validate(updated(state, scenario=campaign_meta))


def test_check_game_refuses_a_hub_with_a_one_shot_meta() -> None:
    engine, state = initialized()
    world = state.payload
    hub_payload = world.model_copy(
        update={
            "hub": world.run.place,
            "board": (
                Offer(title="Job One", pitch="I take job one."),
                Offer(title="Job Two", pitch="I take job two."),
            ),
        }
    )
    with pytest.raises(ValueError, match="one-shot"):
        engine.validate(updated(state, payload=hub_payload))
