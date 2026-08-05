from random import Random

from story_test_support import grown, story_game

from aidm.core.base import PLAYER_ID, EntityId
from aidm.core.effects import AddTag, AdjustCounter
from aidm.core.engine import Engine
from aidm.core.plan import OutcomeBranch
from aidm.core.sheet import ChangeCounter, SetNumber, Sheet, SheetDelta, player_sheet, sheet_of
from aidm.core.world import GameState
from aidm.engines.story.actions import Risk, StoryPlan
from aidm.engines.story.advance import GROWTH_REQUIRED

SPEND = ChangeCounter(why="the marks are spent", key="growth", delta=-GROWTH_REQUIRED)
RAT = EntityId("cloister_rat")
STRONG = OutcomeBranch(
    outcome="strong",
    effects=(AddTag(entity_id=PLAYER_ID, tag_id="sure-footed", name="Sure-footed"),),
)
SETBACK = OutcomeBranch(
    outcome="setback",
    effects=(
        AdjustCounter(entity_id=PLAYER_ID, counter="stress", delta=2, reason="the door holds"),
    ),
)


def _plan(**action: object) -> StoryPlan:
    return StoryPlan(
        intent="Kael forces the vault door.",
        tone="strained",
        branches=(STRONG, SETBACK),
        action=Risk.model_validate(
            {"approach": "bold", "difficulty": "risky", "stakes": "forcing the door"} | action
        ),
    )


def _certain(state: GameState[Sheet], bonus: int) -> GameState[Sheet]:
    """2d6 spans 2..12, so an approach this far out of range fixes the outcome under any seed."""
    draft = state.draft()
    player_sheet(draft).numbers["bold"] = bonus
    return draft.committed()


def test_a_risk_rolls_once_against_seven_and_applies_only_the_branch_it_landed_on() -> None:
    engine, state = story_game()
    draft = _certain(state, 8).draft()

    facts = engine.resolve_action(draft, _plan(actor_id=PLAYER_ID), Random(3))

    (rolled,) = [fact for fact in facts if fact.kind == "dice_rolled"]
    assert (rolled.data["vs"], rolled.data["success"]) == (7, True)
    assert [fact.kind for fact in facts] == ["dice_rolled", "tag_added"]
    sheet = sheet_of(draft, PLAYER_ID)
    assert sheet.tag("sure-footed") is not None
    assert sheet.counters["growth"].current == 0


def test_a_setback_on_the_player_marks_growth_the_model_never_writes() -> None:
    engine, state = story_game()
    draft = _certain(state, -7).draft()

    facts = engine.resolve_action(draft, _plan(actor_id=PLAYER_ID), Random(3))

    assert [fact.kind for fact in facts] == ["dice_rolled", "counter_changed", "counter_changed"]
    sheet = sheet_of(draft, PLAYER_ID)
    assert sheet.counters["growth"].current == 1
    assert sheet.counters["stress"].current == 2
    assert sheet.tag("sure-footed") is None


def test_check_plan_refuses_what_the_procedure_cannot_resolve() -> None:
    """A tag must be held to count; whether a held tag helps or hinders stays the model's call."""
    engine, state = story_game()
    gear = _plan(actor_id=PLAYER_ID, helping_tag_id="unsteady-lantern")

    assert engine.check_plan(state, gear) is None
    assert "not here with the player" in _refusal(engine, state, _plan(actor_id=RAT))
    absent = _plan(actor_id=PLAYER_ID, helping_tag_id="lockpicking")
    assert "nothing helps them here" in _refusal(engine, state, absent)
    hinders = _plan(actor_id=PLAYER_ID, hindering_tag_id="unsteady-lantern")
    assert "nothing hinders them here" in _refusal(engine, state, hinders)

    quiet = StoryPlan(intent="Kael listens.", tone="still", branches=(STRONG,))
    assert "settles no outcome" in _refusal(engine, state, quiet)

    taken_out = state.draft()
    player_sheet(taken_out).counters["stress"].current = 5
    assert "TAKEN OUT" in _refusal(engine, taken_out.committed(), _plan(actor_id=PLAYER_ID))


def test_growth_opens_an_offer_and_storys_own_caps_refuse_what_breaks_them() -> None:
    engine, state = story_game()
    assert engine.proposal.offered(state) is None

    ready = grown(state)
    offer = engine.proposal.offered(ready)
    assert offer is not None

    legal = SheetDelta(changes=(SetNumber(why="patience earned", key="clever", value=2), SPEND))
    over_cap = SheetDelta(changes=(SetNumber(why="greed", key="bold", value=4), SPEND))
    unspent = SheetDelta(changes=(SetNumber(why="free lunch", key="clever", value=2),))

    assert engine.proposal.check(ready, offer, legal) is None
    assert engine.proposal.check(ready, offer, over_cap) == "an approach cannot pass +3: ['bold']"
    assert "must be spent" in str(engine.proposal.check(ready, offer, unspent))


def test_the_one_action_is_worked_through_in_the_directors_instructions() -> None:
    """An action without an example teaches the model nothing: coverage is asserted, not hoped."""
    engine, _ = story_game()

    assert engine.director_instructions.count('"act": "risk"') == 1


def _refusal(engine: Engine[Sheet], state: GameState[Sheet], plan: StoryPlan) -> str:
    refused = engine.check_plan(state, plan)
    assert refused is not None
    return refused
