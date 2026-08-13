from random import Random

from core_test_support import capability, initialized
from loner3e_test_support import at_milestone

from aidm.engines.counters import CounterChange
from aidm.engines.loader import Engine
from aidm.engines.loner3e.actions import Question
from aidm.engines.loner3e.advance import Milestone
from aidm.engines.loner3e.mechanics import LUCK_MAX, TIES_PER_TWIST, read, write
from aidm.engines.loner3e.resolve import (
    HARM,
    TWIST_TABLE,
    defeat_note,
    outcome_for,
    resolve_question,
    twist_note,
    twist_pairing,
)
from aidm.engines.loner3e.rules import LABELS
from aidm.state.base import PLAYER_ID, EntityId
from aidm.state.effects import TraitChange
from aidm.state.plan import OutcomeBranch, TurnPlanBase
from aidm.state.world import GameState

YES_AND = OutcomeBranch(
    outcome="yes-and",
    effects=(TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="sure-footed"),),
)
FOE = EntityId("mara")
NO_AND = OutcomeBranch(
    outcome="no-and",
    effects=(
        CounterChange(
            mode="adjust",
            entity_id=PLAYER_ID,
            counter="luck",
            amount=-1,
            why="the seal takes something out of him",
        ),
    ),
)


def _plan(engine: Engine, **action: object) -> TurnPlanBase:
    return engine.plan_type.model_validate(
        {
            "branches": (YES_AND, NO_AND),
            "action": {
                "act": "question",
                "question": "Does he get the seal open before the whispering finds him?",
                "leverage": [],
                "trouble": [],
                "opponent_id": None,
            }
            | action,
        }
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
            tally[outcome] = tally.get(outcome, 0) + 1
    assert tally == {
        "yes-and": 3,
        "yes": 9,
        "yes-but": 9,
        "no-but": 3,
        "no": 9,
        "no-and": 3,
    }
    assert set(tally) == LABELS


def test_the_twist_table_reads_a_subject_off_one_die_and_an_action_off_the_other() -> None:
    """The SRD's own worked example: a twist roll of (4, 2)."""
    assert len(TWIST_TABLE) == 6
    assert twist_pairing(4, 2) == ("A physical event", "Alters the location")
    assert "A PHYSICAL EVENT / ALTERS THE LOCATION" in twist_note(*twist_pairing(4, 2))


def test_a_question_rolls_two_dice_and_applies_only_the_branch_it_landed_on() -> None:
    engine, state = initialized()
    draft = state.draft()

    facts = engine.resolve_action(draft, _plan(engine, actor_id=PLAYER_ID), Random(17))

    assert [fact.kind for fact in facts] == [
        "dice_rolled",
        "dice_rolled",
        "question_answered",
        "trait_added",
    ]
    assert draft.world.require(PLAYER_ID).trait("sure-footed") is not None
    assert read(draft).sheets[PLAYER_ID].luck.current == LUCK_MAX


def test_check_plan_owes_the_model_every_refusal_the_resolve_raises() -> None:
    engine, state = initialized()
    sheet_tag = _plan(engine, actor_id=PLAYER_ID, leverage=["Reads Old Stonework"])
    scene_tag = _plan(engine, actor_id=PLAYER_ID, leverage=["Unsteady Lantern"])
    assert engine.check_plan(state, sheet_tag) is None
    assert engine.check_plan(state, scene_tag) is None

    invented = _plan(engine, actor_id=PLAYER_ID, leverage=["Silver Tongue"])
    assert "has no tag" in _refusal(engine, state, invented)

    quiet = engine.plan_type.model_validate({"branches": (YES_AND,)})
    assert "settles no outcome" in _refusal(engine, state, quiet)

    elsewhere = _plan(engine, actor_id=PLAYER_ID, opponent_id="cloister_rat")
    assert "is not here with the player" in _refusal(engine, state, elsewhere)
    alone = _plan(engine, actor_id=PLAYER_ID, opponent_id=PLAYER_ID)
    assert "their own opposition" in _refusal(engine, state, alone)


def test_a_tag_named_twice_buys_no_more_than_naming_it_once() -> None:
    _, state = initialized()
    trouble = ("Never Walks Away", "Marked by the Past")

    once = Question(
        actor_id=PLAYER_ID,
        question="Does he force the seal before the whispering finds him?",
        leverage=("Pry Bar",),
        trouble=trouble,
    )
    twice = once.model_copy(update={"leverage": ("Pry Bar", "Pry Bar")})

    for action in (once, twice):
        draft = state.draft()
        facts, _ = resolve_question(draft, action, Random(1))
        (answered,) = [fact for fact in facts if fact.kind == "question_answered"]
        assert answered.data["position"] == "disadvantage"


def test_a_tie_ticks_the_twist_and_the_third_tie_calls_one() -> None:
    _, state = initialized()
    draft = state.draft()
    mechanics = read(draft)
    mechanics.twist.current = TIES_PER_TWIST - 1
    write(draft, mechanics)
    primed = draft.committed()

    action = Question(actor_id=PLAYER_ID, question="Does he slip past unheard?")
    for seed in range(200):
        draft = primed.draft()
        facts, _ = resolve_question(draft, action, Random(seed))
        (answered,) = [fact for fact in facts if fact.kind == "question_answered"]
        if answered.data["chance"] == answered.data["risk"]:
            break
    else:
        raise AssertionError("no seed under 200 tied the dice")

    (due,) = [fact for fact in facts if fact.kind == "twist_due"]
    rolled = twist_note(str(due.data["subject"]), str(due.data["action"]))
    assert read(draft).twist.current == 0
    assert rolled in draft.world.pending_notes


def test_a_conflict_exchange_moves_luck_off_whichever_side_lost_it() -> None:
    _, state = initialized()
    assert set(HARM) == LABELS

    for seed in range(200):
        draft = state.draft()
        facts, outcome = resolve_question(draft, _duel(), Random(seed))
        sheets = read(draft).sheets
        harm = HARM[outcome]
        loser = FOE if harm > 0 else PLAYER_ID
        assert sheets[loser].luck.current == LUCK_MAX - abs(harm)
        assert sheets[FOE if loser == PLAYER_ID else PLAYER_ID].luck.current == LUCK_MAX
        assert not any(fact.kind == "twist_due" for fact in facts)
        assert read(draft).twist.current == 0


def test_luck_running_out_ends_the_conflict_and_refuses_another_exchange() -> None:
    engine, state = initialized()
    draft = state.draft()
    mechanics = read(draft)
    mechanics.sheets[FOE].luck.current = 1
    write(draft, mechanics)
    hurt = draft.committed()

    for seed in range(200):
        draft = hurt.draft()
        facts, outcome = resolve_question(draft, _duel(), Random(seed))
        if HARM[outcome] > 0:
            break
    else:
        raise AssertionError("no seed under 200 answered yes")

    assert read(draft).sheets[FOE].luck.current == 0
    assert any(fact.kind == "conflict_lost" for fact in facts)
    assert defeat_note(draft.world.require(FOE).name) in draft.world.pending_notes

    spent = draft.committed()
    again = _plan(engine, actor_id=PLAYER_ID, opponent_id=FOE)
    assert "already out of luck" in _refusal(engine, spent, again)


def test_a_milestone_opens_an_offer_and_the_caps_refuse_what_breaks_them() -> None:
    engine, state = initialized()
    advancement = capability(engine)
    assert advancement.offered(state) is None

    ready = at_milestone(state)
    offer = advancement.offered(ready)
    assert offer is not None

    legal = Milestone(
        change="skill", tag="Reads a Second Tongue", why="the old texts finally make sense"
    )
    rewrite = Milestone(
        change="rewrite",
        tag="Never Walks Away",
        into="Knows When to Walk Away",
        why="the vault taught him the cost",
    )
    unwritten = rewrite.model_copy(update={"tag": "Never Held a Blade"})

    assert advancement.violation(ready, offer, legal) is None
    assert advancement.violation(ready, offer, rewrite) is None
    assert advancement.violation(ready, offer, unwritten) == (
        "Kael carries no tag 'Never Held a Blade' to rewrite"
    )


def test_the_one_action_is_worked_through_in_the_directors_instructions() -> None:
    """An action without an example teaches the model nothing: coverage is asserted, not hoped."""
    engine, _ = initialized()

    assert engine.director_instructions.count('"act": "question"') == 1


def _refusal(engine: Engine, state: GameState, plan: TurnPlanBase) -> str:
    refused = engine.check_plan(state, plan)
    assert refused is not None
    return refused
