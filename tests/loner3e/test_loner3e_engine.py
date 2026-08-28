from random import Random

import pytest
from core_test_support import at_boundary, initialized, sheet_of
from pydantic import ValidationError

from aidm.engines.core import rules
from aidm.engines.loner3e.engine import advance, load_packs
from aidm.engines.loner3e.rules import (
    RULES,
    SRD_PACK,
    AdventureGrowth,
    Change,
    Question,
    Sheet,
    apply_restore_luck,
    conflict_prompt,
    defeat_note,
    outcome_for,
    resolve_question,
    twist_note,
    twist_pairing,
    twist_table,
)
from aidm.state.entities import PLAYER_ID, Counter, Entity, EntityId
from aidm.state.facts import EventBadge, player_events
from aidm.state.play import PendingDecision

TWISTS = twist_table(load_packs(), SRD_PACK)
FOE = EntityId("mara")
LANTERN = EntityId("lantern")


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
    assert len(TWISTS) == 6
    assert twist_pairing(4, 2, TWISTS) == ("A physical event", "Alters the location")
    assert "A PHYSICAL EVENT / ALTERS THE LOCATION" in twist_note(*twist_pairing(4, 2, TWISTS))


def test_a_question_puts_two_dice_to_the_answer_and_costs_no_luck_on_its_own() -> None:
    _, state = initialized()
    draft = state.draft()

    facts = resolve_question(draft, _seal(), Random(17), TWISTS)

    assert [fact.kind for fact in facts] == ["dice_rolled", "dice_rolled", "question_answered"]
    assert sheet_of(draft, PLAYER_ID, Sheet).luck.current == RULES.luck_max


def test_a_question_the_fiction_cannot_carry_is_refused_with_the_reason() -> None:
    _, state = initialized()

    elsewhere = _seal(opponent_id="cloister-rat")
    with pytest.raises(ValueError, match="is not here with the player"):
        _ = resolve_question(state.draft(), elsewhere, Random(0), TWISTS)
    with pytest.raises(ValueError, match="their own opposition"):
        _ = resolve_question(state.draft(), _seal(opponent_id=PLAYER_ID), Random(0), TWISTS)


def test_the_judged_position_is_what_reaches_the_dice_and_the_record() -> None:
    _, state = initialized()
    action = Question(
        actor_id=PLAYER_ID,
        question="Does he force the seal before the whispering finds him?",
        position="disadvantage",
        edge="Never Walks Away",
    )

    facts = resolve_question(state.draft(), action, Random(1), TWISTS)

    (oracle,) = player_events(facts)
    assert oracle.badges == (
        EventBadge(label="Position", value="Disadvantage"),
        EventBadge(label="Edge", value="Never Walks Away"),
    )
    assert oracle.dice[1].faces == (6, 6)


def test_a_tie_ticks_the_twist_and_the_third_tie_calls_one() -> None:
    _, state = initialized()
    draft = state.draft()
    with rules(draft.player, Sheet) as sheet:
        sheet.twist.current = RULES.ties_per_twist - 1
    primed = draft.committed()

    action = Question(actor_id=PLAYER_ID, question="Does he slip past unheard?")
    for seed in range(200):
        draft = primed.draft()
        facts = resolve_question(draft, action, Random(seed), TWISTS)
        if any(fact.kind == "twist_due" for fact in facts):
            break
    else:
        raise AssertionError("no seed under 200 tied the dice")

    _, twist = player_events(facts)
    subject = next(badge.value for badge in twist.badges if badge.label == "Subject")
    action_name = next(badge.value for badge in twist.badges if badge.label == "Action")
    rolled = twist_note(subject, action_name)
    assert sheet_of(draft, PLAYER_ID, Sheet).twist.current == 0
    assert rolled in draft.world.pending_notes


def test_a_conflict_exchange_moves_luck_off_whichever_side_lost_it() -> None:
    _, state = initialized()
    # Every answer the ladder can give costs somebody luck in a conflict.
    ladder = {outcome_for(chance, risk) for chance in range(1, 7) for risk in range(1, 7)}
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
        facts = resolve_question(draft, _duel(), Random(seed), TWISTS)
        (oracle,) = player_events(facts)
        harm = outcome_for(oracle.dice[0].kept, oracle.dice[1].kept).harm
        loser, held = (FOE, PLAYER_ID) if harm > 0 else (PLAYER_ID, FOE)
        assert sheet_of(draft, loser, Sheet).luck.current == RULES.luck_max - abs(harm)
        assert sheet_of(draft, held, Sheet).luck.current == RULES.luck_max
        # A tie still ticks the counter inside a conflict; one tie alone never reaches the twist.
        assert not any(fact.kind == "twist_due" for fact in facts)
        tied = oracle.dice[0].kept == oracle.dice[1].kept
        assert sheet_of(draft, PLAYER_ID, Sheet).twist.current == (1 if tied else 0)


def test_luck_running_out_ends_the_conflict_and_resets_both_pools() -> None:
    _, state = initialized()
    draft = state.draft()
    # A 10-max pool proves the reset lands on the sheet's own maximum, not on a +luck_max delta.
    with rules(draft.world.require(FOE), Sheet) as sheet:
        sheet.luck = Counter(current=1, maximum=10)
    hurt = draft.committed()

    for seed in range(200):
        draft = hurt.draft()
        facts = resolve_question(draft, _duel(), Random(seed), TWISTS)
        (oracle,) = player_events(facts)
        if outcome_for(oracle.dice[0].kept, oracle.dice[1].kept).harm > 0:
            break
    else:
        raise AssertionError("no seed under 200 answered yes")

    assert sheet_of(draft, FOE, Sheet).luck.current == 10
    assert sheet_of(draft, PLAYER_ID, Sheet).luck.current == RULES.luck_max
    assert any(fact.kind == "conflict_lost" for fact in facts)
    assert defeat_note(draft.world.require(FOE).name) in draft.world.pending_notes
    # The conflict is over, so the defeat note steers the same run instead of handing control back.
    assert draft.pending is None


def test_an_exchange_both_sides_survive_hands_the_next_key_action_to_the_player() -> None:
    _, state = initialized()
    draft = state.draft()

    _ = resolve_question(draft, _duel(), Random(0), TWISTS)

    decision = draft.pending
    assert decision is not None
    foe = draft.world.require(FOE)
    expected = conflict_prompt(draft, draft.player, foe)
    assert (decision.kind, decision.prompt) == ("conflict", expected)
    assert foe.name in decision.prompt
    assert decision.options == ()


def test_a_thing_fights_back_with_a_sheet_of_its_own_when_it_is_here() -> None:
    _, state = initialized()
    draft = state.draft()

    facts = resolve_question(draft, _seal(opponent_id=LANTERN), Random(0), TWISTS)

    assert any(fact.kind == "question_answered" for fact in facts)
    lantern = sheet_of(draft, LANTERN, Sheet).luck.current
    assert min(lantern, sheet_of(draft, PLAYER_ID, Sheet).luck.current) < RULES.luck_max

    away = state.draft()
    away.world.require(LANTERN).parent_id = EntityId("cloister")
    with pytest.raises(ValueError, match="is not here with the player"):
        _ = resolve_question(away, _seal(opponent_id=LANTERN), Random(0), TWISTS)


def test_the_engine_plays_the_hand_back_and_refuses_every_other_decision() -> None:
    engine, _ = initialized()
    hand_back = PendingDecision(
        kind="conflict",
        prompt="Say your next key action.",
        options=(),
        allows_text=True,
        payload={},
    )

    engine.check_pending(hand_back)

    with pytest.raises(ValueError, match="cannot play a 'defence' decision"):
        engine.check_pending(hand_back.model_copy(update={"kind": "defence"}))
    with pytest.raises(ValidationError):
        engine.check_pending(hand_back.model_copy(update={"payload": {"outcome": "no"}}))


def test_an_actor_already_at_zero_luck_refuses_another_exchange() -> None:
    _, state = initialized()
    draft = state.draft()
    with rules(draft.world.require(FOE), Sheet) as sheet:
        sheet.luck.current = 0
    spent = draft.committed()

    with pytest.raises(ValueError, match="already out of luck"):
        _ = resolve_question(spent.draft(), _duel(), Random(0), TWISTS)


def test_an_adventures_end_owes_an_advance_and_a_tag_the_sheet_lacks_is_refused() -> None:
    engine, state = initialized()
    assert engine.owed_notes(state) == ()

    ready = at_boundary(state, Sheet)
    (owed,) = engine.owed_notes(ready)
    assert ready.player.name in owed

    rewrite = AdventureGrowth(
        subject_id=PLAYER_ID,
        changes=(
            Change(
                kind="rewrite",
                tag="Never Walks Away",
                into="Knows When to Walk Away",
                why="the vault taught him the cost",
            ),
        ),
    )
    assert advance(ready.draft(), rewrite, Random(0))

    unwritten = AdventureGrowth(
        subject_id=PLAYER_ID,
        changes=(
            Change(
                kind="rewrite",
                tag="Never Held a Blade",
                into="Holds It Well",
                why="a tag the sheet does not carry",
            ),
        ),
    )
    with pytest.raises(ValueError, match="carries no tag 'Never Held a Blade'"):
        _ = advance(ready.draft(), unwritten, Random(0))


def test_an_npc_party_members_growth_writes_their_own_sheet_not_the_players() -> None:
    engine, state = initialized()
    grow_mara = AdventureGrowth(
        subject_id=FOE,
        changes=(
            Change(kind="skill", tag="Reads Old Stonework", why="she has read enough of it now"),
        ),
    )
    with pytest.raises(ValueError, match="is not in the party"):
        _ = advance(at_boundary(state, Sheet).draft(), grow_mara, Random(0))

    draft = state.draft()
    draft.world.party.append(FOE)
    ready = at_boundary(draft.committed(), Sheet)
    assert len(engine.owed_notes(ready)) == 2

    draft = ready.draft()
    facts = advance(draft, grow_mara, Random(0))
    grown = draft.committed()

    assert sheet_of(grown, FOE, Sheet).skills[-1] == "Reads Old Stonework"
    assert sheet_of(grown, PLAYER_ID, Sheet).skills == sheet_of(ready, PLAYER_ID, Sheet).skills
    assert [fact.kind for fact in facts] == ["skill_gained", "milestone_spent"]


def test_an_actor_who_joins_after_an_adventure_is_not_owed_the_growth_they_missed() -> None:
    engine, state = initialized()
    ready = at_boundary(state, Sheet)
    draft = ready.draft()
    newcomer = Entity(
        id=EntityId("newcomer"),
        kind="actor",
        name="A Newcomer",
        brief="Falls in beside Kael.",
        known=True,
        parent_id=draft.player_location,
        rules={"concept": "A Newcomer"},
    )
    _ = draft.add(newcomer)
    draft.world.party.append(newcomer.id)
    walked_in = draft.committed()

    engine.validate(walked_in)
    (owed,) = engine.owed_notes(walked_in)
    assert walked_in.player.name in owed


def test_a_closed_chapter_gates_the_advance_and_a_second_one_earns_another() -> None:
    engine, state = initialized()
    change = AdventureGrowth(
        subject_id=PLAYER_ID,
        changes=(Change(kind="gear", tag="Waxed Rope", why="he never climbs without it now"),),
    )
    draft = at_boundary(state, Sheet).draft()
    _ = advance(draft, change, Random(0))
    spent = draft.committed()

    assert engine.owed_notes(spent) == ()
    with pytest.raises(ValueError, match="has no advance owed"):
        _ = advance(spent.draft(), change, Random(0))
    assert len(engine.owed_notes(at_boundary(spent, Sheet))) == 1


def test_an_adventure_growth_with_three_changes_lands_all_three_on_the_sheet() -> None:
    _, state = initialized()
    ready = at_boundary(state, Sheet)

    growth = AdventureGrowth(
        subject_id=PLAYER_ID,
        changes=(
            Change(kind="skill", tag="Reads Tide Marks", why="the vault left its mark on him"),
            Change(kind="gear", tag="Waxed Rope", why="he never climbs without it now"),
            Change(kind="frailty", tag="Flinches at the Dark", why="the dark held too long"),
        ),
    )
    draft = ready.draft()
    facts = advance(draft, growth, Random(0))
    grown = draft.committed()

    sheet = sheet_of(grown, PLAYER_ID, Sheet)
    assert (sheet.skills[-1], sheet.gear[-1], sheet.frailties[-1]) == (
        "Reads Tide Marks",
        "Waxed Rope",
        "Flinches at the Dark",
    )
    assert [fact.kind for fact in facts] == [
        "skill_gained",
        "gear_gained",
        "frailty_gained",
        "milestone_spent",
    ]


def test_restoring_luck_that_is_already_full_is_a_quiet_no_op() -> None:
    _, state = initialized()

    assert apply_restore_luck(state.draft(), PLAYER_ID) == []
