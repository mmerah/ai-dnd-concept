from random import Random

import pytest
from core_test_support import (
    TWENTYFOURXX,
    at_boundary,
    game,
    played,
    scripted,
    text,
    tool_call,
)
from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from aidm.engines.core import DirectorContext, Engine, TurnRecord
from aidm.engines.twentyfourxx.engine import TwentyfourxxEngine, director_toolset
from aidm.engines.twentyfourxx.rules import (
    Advance,
    Attempt,
    Defence,
    LuckTest,
    Mechanics,
    Sheet,
    StakedAttempt,
    apply_change_credits,
    apply_complete_chapter,
    outcome_for,
    pool_faces,
    resolve_attempt,
    resolve_luck_test,
    resolve_stake,
)
from aidm.state.creation import Picks
from aidm.state.entities import PLAYER_ID, EntityId
from aidm.state.facts import Fact, player_events
from aidm.state.model import Game
from aidm.state.play import Answer, DecisionOption, PendingDecision

MARA = EntityId("mara")
LANTERN = EntityId("lantern")
RISK = "The hinges may take your hand with them."
# The seed on which Kael's own attempt is a disaster: the hit that hands him the defence.
HIT = 2


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
    assert pool_faces(sheet, action, None) == expected


def test_a_helper_rolls_their_own_skill_die_into_the_pool() -> None:
    sheet = Sheet(skills={"Climbing": 10})
    helper = Sheet(skills={"Hacking": 12})
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="climb the wall",
        skill="Climbing",
        helper_id=MARA,
        helper_skill="Hacking",
    )
    assert pool_faces(sheet, action, helper) == (10, 12)


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


def test_an_attempt_is_refused_before_it_rolls_when_the_skill_is_not_on_the_sheet() -> None:
    _, state = game(TWENTYFOURXX)

    unknown_skill = Attempt(actor_id=PLAYER_ID, goal="Kael picks the lock.", skill="Lockpicking")
    with pytest.raises(ValueError) as skill_error:
        resolve_attempt(state.draft(), unknown_skill, Random(0))
    message = str(skill_error.value)
    assert "Climbing" in message
    assert "Stealth" in message
    assert "Tracking" in message


def test_an_ally_who_lacks_the_named_skill_is_refused() -> None:
    _, state = game(TWENTYFOURXX)
    action = Attempt(
        actor_id=PLAYER_ID,
        goal="Kael picks the lock while Mara covers the door.",
        helper_id=MARA,
        helper_skill="Lockpicking",
    )
    with pytest.raises(ValueError, match="helper_skill"):
        resolve_attempt(state.draft(), action, Random(0))


async def test_roll_attempt_narrows_skill_and_helper_skill_to_who_is_here() -> None:
    engine, state = game(TWENTYFOURXX)
    ctx = RunContext(
        deps=DirectorContext(engine=engine, draft=state, rng=Random(0), log=TurnRecord()),
        model=TestModel(),
        usage=RunUsage(),
    )

    tools = await director_toolset().get_tools(ctx)
    schema = tools["roll_attempt"].tool_def.parameters_json_schema

    # Only Kael's local skills qualify; Mara has none and the rat is elsewhere.
    expected = ["", "Climbing", "Stealth", "Tracking"]
    assert schema["properties"]["skill"]["enum"] == expected
    assert schema["properties"]["helper_skill"]["enum"] == expected

    staked = tools["stake_attempt"].tool_def.parameters_json_schema
    assert staked["properties"]["skill"]["enum"] == expected


def test_naming_both_an_ally_and_a_helped_tag_is_refused_at_the_schema() -> None:
    with pytest.raises(ValidationError):
        Attempt(
            actor_id=PLAYER_ID,
            goal="Kael picks the lock.",
            helper_id=MARA,
            helped="a steady rope",
        )


def test_a_job_raises_one_skill_a_step_and_pays_rolled_credits() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = engine.advancement
    ready = at_boundary(state)
    (offer,) = advancement.offers(ready)
    before = Mechanics.of_game(ready).sheets[PLAYER_ID]

    raise_existing = Advance(skill="Tracking", why="the climb taught them the route")
    draft = ready.draft()
    facts = advancement.resolve(draft, offer, raise_existing, Random(3))
    grown = draft.committed()

    sheet = Mechanics.of_game(grown).sheets[PLAYER_ID]
    assert sheet.skills["Tracking"] == 10
    assert sheet.jobs.current == before.jobs.current + 1
    (dice_fact,) = [fact for fact in facts if fact.kind == "dice_rolled"]
    paid = sheet.credits.current - before.credits.current
    assert dice_fact.trace.endswith(f"-> {paid}")

    take_new = Advance(skill="Lockpicking", why="the job called for it")
    draft = ready.draft()
    advancement.resolve(draft, offer, take_new, Random(4))
    grown = Mechanics.of_game(draft.committed())
    assert grown.sheets[PLAYER_ID].skills["Lockpicking"] == 8


def test_an_advance_is_offered_only_once_a_job_is_recorded() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = engine.advancement
    assert advancement.offers(state) == ()

    draft = state.draft()
    apply_complete_chapter(draft)
    after = draft.committed()

    (offer,) = advancement.offers(after)
    assert offer.subject_id == PLAYER_ID


def test_a_skill_already_at_d12_is_refused_and_the_refusal_reaches_the_advisor() -> None:
    engine, state = game(TWENTYFOURXX)
    advancement = engine.advancement
    ready = at_boundary(state)

    draft = ready.draft()
    mechanics = Mechanics.of_game(draft)
    mechanics.sheets[PLAYER_ID].skills["Climbing"] = 12
    maxed = draft.committed()

    (offer,) = advancement.offers(maxed)
    capped = Advance(skill="Climbing", why="there is nowhere higher to climb")

    message = advancement.advance_refusal(maxed, offer, capped)
    assert message is not None
    assert "d12" in message


def test_credits_are_paid_charged_and_never_overdrawn() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()
    sheet = Mechanics.of_game(draft).sheets[PLAYER_ID]
    before = sheet.credits.current

    paid = apply_change_credits(draft, PLAYER_ID, 3)
    assert [fact.kind for fact in paid] == ["counter_changed"]
    assert sheet.credits.current == before + 3

    with pytest.raises(ValueError, match="cannot be spent"):
        _ = apply_change_credits(draft, PLAYER_ID, -(before + 4))
    assert sheet.credits.current == before + 3

    with pytest.raises(ValueError, match="zero moves nothing"):
        _ = apply_change_credits(draft, PLAYER_ID, 0)


def _tested(resolution: tuple[Fact, ...]) -> Fact:
    return next(fact for fact in resolution if fact.kind == "luck_tested")


def test_a_tested_bad_luck_risk_that_lands_leaves_a_note_for_the_next_turn() -> None:
    _, state = game(TWENTYFOURXX)
    action = Attempt(
        actor_id=PLAYER_ID, goal="Kael tries something risky.", luck_test="running out of oil"
    )

    draft = state.draft()
    facts = resolve_attempt(draft, action, Random(2))
    (card,) = player_events(facts)
    luck = next(die for die in card.dice if die.label == "Luck")
    assert 1 <= luck.kept <= 4
    assert len(draft.world.pending_notes) == 1
    assert any(fact.kind == "luck_tested" for fact in facts)

    draft = state.draft()
    facts = resolve_attempt(draft, action, Random(1))
    assert draft.world.pending_notes == state.world.pending_notes == ()
    assert not any(fact.kind == "luck_tested" for fact in facts)


def test_a_standalone_luck_test_needs_no_attempt_and_only_bad_luck_leaves_a_note() -> None:
    _, state = game(TWENTYFOURXX)
    action = LuckTest(actor_id=PLAYER_ID, subject="running out of oil")

    draft = state.draft()
    trouble = resolve_luck_test(draft, action, Random(2))
    assert _tested(trouble).trace.endswith(": trouble")
    assert len(draft.world.pending_notes) == 1

    signs = resolve_luck_test(state.draft(), action, Random(0))
    assert _tested(signs).trace.endswith(": signs of it")

    draft = state.draft()
    clear = resolve_luck_test(draft, action, Random(5))
    assert not any(fact.kind == "luck_tested" for fact in clear)
    assert draft.world.pending_notes == ()


def _forcing(**args: object) -> Attempt:
    return Attempt.model_validate(
        {"actor_id": PLAYER_ID, "goal": "Kael forces the vault door", "skill": "Climbing"} | args
    )


def _staked_forcing(**args: object) -> StakedAttempt:
    return StakedAttempt.model_validate(
        {
            "actor_id": PLAYER_ID,
            "goal": "Kael forces the vault door",
            "skill": "Climbing",
            "risk": RISK,
        }
        | args
    )


def _waiting(draft: Game) -> PendingDecision:
    decision = draft.pending
    assert decision is not None
    return decision


def _hit(state: Game) -> tuple[Game, PendingDecision]:
    """A draft carrying the defence decision Kael's own disaster opened, ready to be answered."""
    draft = state.draft()
    _ = resolve_attempt(draft, _forcing(), Random(HIT))
    decision = _waiting(draft)
    draft.pending = None
    return draft, decision


async def _offered(
    engine: Engine, state: Game, answered: PendingDecision | None, *, settled: bool = False
) -> set[str]:
    landed = [Fact(kind="defence_taken", trace="the hit lands in full")] if settled else []
    deps = DirectorContext(
        engine=engine, draft=state, rng=Random(0), log=TurnRecord(facts=landed), answered=answered
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
    return set(await director_toolset().get_tools(ctx))


def test_a_stake_freezes_a_playable_attempt_and_waits_on_the_player() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    assert resolve_stake(draft, _staked_forcing()) == ()

    decision = _waiting(draft)
    assert (decision.kind, decision.prompt, decision.free_text) == ("stake", RISK, True)
    assert [option.id for option in decision.options] == ["proceed"]
    assert StakedAttempt.model_validate(decision.payload) == _staked_forcing()


def test_a_stake_on_an_npc_attempt_is_refused() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    with pytest.raises(ValueError, match="the player's own"):
        _ = resolve_stake(draft, _staked_forcing(actor_id="mara"))
    assert draft.pending is None


def test_a_stake_on_an_attempt_the_sheet_cannot_carry_freezes_nothing() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    with pytest.raises(ValueError, match="no skill 'Lockpicking'"):
        _ = resolve_stake(draft, _staked_forcing(skill="Lockpicking"))
    assert draft.pending is None


def test_proceeding_rolls_the_frozen_attempt_and_a_hit_hands_back_the_defence() -> None:
    engine, state = game(TWENTYFOURXX)
    draft = state.draft()
    _ = resolve_stake(draft, _staked_forcing())
    staked = _waiting(draft)
    draft.pending = None

    facts = engine.resume(draft, staked, "proceed", Random(HIT))

    (resolved,) = [fact for fact in facts if fact.kind == "attempt_resolved"]
    assert resolved.trace.endswith("-> disaster")
    decision = _waiting(draft)
    assert decision.kind == "defence"
    assert [option.id for option in decision.options] == ["lantern", "take-it"]
    assert Defence.model_validate(decision.payload) == Defence(
        outcome="disaster", goal=_forcing().goal
    )


def test_breaking_an_item_turns_the_hit_and_that_item_is_never_offered_again() -> None:
    engine, state = game(TWENTYFOURXX)
    draft, decision = _hit(state)

    facts = engine.resume(draft, decision, "lantern", Random(0))

    assert [fact.kind for fact in facts] == ["trait_added", "defence_turned"]
    assert draft.world.require(LANTERN).trait("broken") is not None
    _ = resolve_attempt(draft, _forcing(), Random(HIT))
    assert [option.id for option in _waiting(draft).options] == ["take-it"]


def test_taking_the_hit_records_it_landing_in_full() -> None:
    engine, state = game(TWENTYFOURXX)
    draft, decision = _hit(state)

    (landed,) = engine.resume(draft, decision, "take-it", Random(0))

    assert landed.kind == "defence_taken"
    assert landed.told
    assert draft.world.require(LANTERN).trait("broken") is None
    assert draft.pending is None


def test_an_npcs_own_disaster_hands_the_player_nothing() -> None:
    _, state = game(TWENTYFOURXX)
    draft = state.draft()

    facts = resolve_attempt(draft, Attempt(actor_id=MARA, goal="Mara shoulders it"), Random(HIT))

    (resolved,) = [fact for fact in facts if fact.kind == "attempt_resolved"]
    assert resolved.trace.endswith("-> disaster")
    assert draft.pending is None


async def test_the_settle_tool_is_offered_once_where_an_answer_consumed_a_defence() -> None:
    engine, state = game(TWENTYFOURXX)
    _, decision = _hit(state)

    assert "settle_defence" not in await _offered(engine, state, None)
    assert "settle_defence" in await _offered(engine, state, decision)
    # One hit is settled once: a second call would break a second item for the same blow.
    assert "settle_defence" not in await _offered(engine, state, decision, settled=True)


async def test_a_hit_the_player_answered_in_their_own_words_is_still_turned() -> None:
    engine, state = game(TWENTYFOURXX)
    draft, decision = _hit(state)
    draft.pending = decision
    suspended = draft.committed()

    result = await played(
        engine,
        suspended,
        Answer(text="I swing the lantern into the gap and let it take the blow."),
        director=FunctionModel(
            scripted(tool_call("settle_defence", item_id="lantern"), text("The glass gives way."))
        ),
    )

    assert [fact.kind for fact in result.turn.facts] == ["trait_added", "defence_turned"]
    assert result.state.world.require(LANTERN).trait("broken") is not None
    assert result.state.pending is None


def test_a_decision_this_engine_cannot_play_or_read_is_refused() -> None:
    engine, _ = game(TWENTYFOURXX)

    with pytest.raises(ValueError, match="cannot play a 'spend-momentum' decision"):
        engine.check_pending(
            PendingDecision(kind="spend-momentum", prompt="Spend a point?", options=(), payload={})
        )
    with pytest.raises(ValidationError):
        engine.check_pending(
            PendingDecision(
                kind="stake",
                prompt=RISK,
                options=(DecisionOption(id="proceed", label="Proceed"),),
                payload={"goal": "an attempt with no actor"},
            )
        )


def test_creation_hands_over_the_kit_as_carried_items_and_lands_the_training_die() -> None:
    creation = TwentyfourxxEngine().creation
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("psychic",),
        "training": ("telepathy-at-d10",),
        "origin": ("human",),
        "skills": ("stealth", "deception", "connections"),
    }
    created = creation.create("Vex", "A quiet reader of rooms.", picks)
    assert [item.name for item in created.profile.items] == ["Comm", "Bottle of PsychOut"]
    assert created.profile.traits == ()
    assert created.rules["skills"] == {
        "Telepathy": 10,
        "Stealth": 8,
        "Deception": 8,
        "Connections": 8,
    }


def test_a_bulky_kit_item_carries_the_bulky_trait() -> None:
    creation = TwentyfourxxEngine().creation
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("tech",),
        "origin": ("human",),
        "skills": ("climbing", "stealth", "tracking"),
    }
    created = creation.create("Wren", "Solders anything.", picks)
    computer = next(item for item in created.profile.items if item.id == "custom-computer")
    assert [trait.id for trait in computer.traits] == ["bulky"]


def test_an_alien_invents_traits_the_menu_never_listed() -> None:
    creation = TwentyfourxxEngine().creation
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("sneak",),
        "origin": ("alien",),
        "traits": ("Wings", "A tail that reads the air"),
    }
    created = creation.create("Ixl", "Feathered and patient.", picks)
    names = [trait.name for trait in created.profile.traits]
    assert names == ["Wings", "A tail that reads the air"]


def test_a_humans_three_increases_can_stack_onto_one_skill() -> None:
    creation = TwentyfourxxEngine().creation
    picks: Picks = {
        "pack": ("srd",),
        "specialty": ("sneak",),
        "origin": ("human",),
        "skills": ("tracking", "tracking", "tracking"),
    }
    created = creation.create("Rho", "Never stops moving.", picks)
    assert created.rules["skills"] == {"Climbing": 8, "Stealth": 8, "Tracking": 12}
