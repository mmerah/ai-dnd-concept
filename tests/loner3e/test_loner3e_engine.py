from random import Random

from core_test_support import capability, initialized
from loner3e_test_support import at_milestone

from aidm.engines.loader import Engine
from aidm.engines.loner3e.actions import (
    HARM,
    Question,
    available_tags,
    defeat_note,
    outcome_for,
    resolve_question,
    twist_note,
    twist_pairing,
)
from aidm.engines.loner3e.advance import Milestone
from aidm.engines.loner3e.mechanics import LUCK_MAX, TIES_PER_TWIST, Mechanics
from aidm.engines.loner3e.pack import SRD_PACK, twist_table
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.state.apply import fire_hooks
from aidm.state.base import PLAYER_ID, Counter, Entity, EntityId
from aidm.state.effects import TraitChange
from aidm.state.facts import CORE, Fact
from aidm.state.plan import DirectorPlan
from aidm.state.world import PARTY_MEMBER, GameState, Hook, HookMatch, Relation

TWISTS = twist_table(Loner3eEngine().packs, SRD_PACK)
SURE_FOOTED = TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="sure-footed")
FOE = EntityId("mara")


def _plan(**args: object) -> DirectorPlan:
    return DirectorPlan.model_validate(
        {
            "focus": "Kael works the sealed door.",
            "effects": ({"name": "trait-change", "args": SURE_FOOTED.model_dump()},),
            "roll": {
                "name": "question",
                "args": {
                    "question": "Does he get the seal open before the whispering finds him?",
                    "leverage": [],
                    "trouble": [],
                    "opponent_id": None,
                }
                | args,
            },
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


def test_the_twist_table_reads_a_subject_off_one_die_and_an_action_off_the_other() -> None:
    """The SRD's own worked example: a twist roll of (4, 2)."""
    assert len(TWISTS) == 6
    assert twist_pairing(4, 2, TWISTS) == ("A physical event", "Alters the location")
    assert "A PHYSICAL EVENT / ALTERS THE LOCATION" in twist_note(*twist_pairing(4, 2, TWISTS))


def test_a_question_rolls_two_dice_before_the_beats_own_effects_land() -> None:
    engine, state = initialized()
    draft = state.draft()

    facts = engine.resolve_beat(draft, _plan(actor_id=PLAYER_ID), Random(17)).facts

    assert [fact.kind for fact in facts] == [
        "dice_rolled",
        "dice_rolled",
        "question_answered",
        "trait_added",
    ]
    assert draft.world.require(PLAYER_ID).trait("sure-footed") is not None
    assert draft.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current == LUCK_MAX


def test_check_beat_owes_the_model_every_refusal_the_resolve_raises() -> None:
    engine, state = initialized()
    sheet_tag = _plan(actor_id=PLAYER_ID, leverage=["Reads Old Stonework"])
    scene_tag = _plan(actor_id=PLAYER_ID, leverage=["Unsteady Lantern"])
    assert engine.check_beat(state, sheet_tag) is None
    assert engine.check_beat(state, scene_tag) is None

    invented = _plan(actor_id=PLAYER_ID, leverage=["Silver Tongue"])
    assert "has no tag" in _refusal(engine, state, invented)

    elsewhere = _plan(actor_id=PLAYER_ID, opponent_id="cloister_rat")
    assert "is not here with the player" in _refusal(engine, state, elsewhere)
    alone = _plan(actor_id=PLAYER_ID, opponent_id=PLAYER_ID)
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
        facts = resolve_question(draft, action, Random(1), TWISTS).facts
        (answered,) = [fact for fact in facts if fact.kind == "question_answered"]
        assert answered.data["position"] == "disadvantage"


def test_a_tie_ticks_the_twist_and_the_third_tie_calls_one() -> None:
    _, state = initialized()
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.twist.current = TIES_PER_TWIST - 1
    primed = draft.committed()

    action = Question(actor_id=PLAYER_ID, question="Does he slip past unheard?")
    for seed in range(200):
        draft = primed.draft()
        facts = resolve_question(draft, action, Random(seed), TWISTS).facts
        (answered,) = [fact for fact in facts if fact.kind == "question_answered"]
        if answered.data["chance"] == answered.data["risk"]:
            break
    else:
        raise AssertionError("no seed under 200 tied the dice")

    (due,) = [fact for fact in facts if fact.kind == "twist_due"]
    rolled = twist_note(str(due.data["subject"]), str(due.data["action"]))
    assert draft.mechanics_as(Mechanics).twist.current == 0
    assert rolled in draft.world.pending_notes


def test_a_conflict_exchange_moves_luck_off_whichever_side_lost_it() -> None:
    _, state = initialized()
    # Every answer the ladder can give costs somebody luck in a conflict.
    assert set(HARM) == {"yes-and", "yes", "yes-but", "no-but", "no", "no-and"}

    for seed in range(200):
        draft = state.draft()
        resolution = resolve_question(draft, _duel(), Random(seed), TWISTS)
        facts, outcome = resolution.facts, resolution.outcome
        assert outcome is not None
        sheets = draft.mechanics_as(Mechanics).sheets
        harm = HARM[outcome]
        loser = FOE if harm > 0 else PLAYER_ID
        assert sheets[loser].luck.current == LUCK_MAX - abs(harm)
        assert sheets[FOE if loser == PLAYER_ID else PLAYER_ID].luck.current == LUCK_MAX
        assert not any(fact.kind == "twist_due" for fact in facts)
        assert draft.mechanics_as(Mechanics).twist.current == 0


def test_luck_running_out_ends_the_conflict_and_resets_both_pools() -> None:
    _, state = initialized()
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    # A 10-max pool proves the reset lands on the sheet's own maximum, not on a +LUCK_MAX delta.
    mechanics.sheets[FOE].luck = Counter(current=1, maximum=10)
    hurt = draft.committed()

    for seed in range(200):
        draft = hurt.draft()
        resolution = resolve_question(draft, _duel(), Random(seed), TWISTS)
        facts, outcome = resolution.facts, resolution.outcome
        assert outcome is not None
        if HARM[outcome] > 0:
            break
    else:
        raise AssertionError("no seed under 200 answered yes")

    sheets = draft.mechanics_as(Mechanics).sheets
    assert sheets[FOE].luck.current == 10
    assert sheets[PLAYER_ID].luck.current == LUCK_MAX
    assert any(fact.kind == "conflict_lost" for fact in facts)
    assert defeat_note(draft.world.require(FOE).name) in draft.world.pending_notes


def test_an_actor_already_at_zero_luck_refuses_another_exchange() -> None:
    engine, state = initialized()
    draft = state.draft()
    mechanics = draft.mechanics_as(Mechanics)
    mechanics.sheets[FOE].luck.current = 0
    spent = draft.committed()

    again = _plan(actor_id=PLAYER_ID, opponent_id=FOE)
    assert "already out of luck" in _refusal(engine, spent, again)


def test_an_opponents_sheet_tags_reach_the_resolver_as_tags_in_play() -> None:
    _, state = initialized()
    draft = state.draft()
    player = draft.world.require(PLAYER_ID)
    player.parent_id = EntityId("cloister")

    tags = available_tags(draft, player, draft.mechanics_as(Mechanics))

    assert "Hard to Frighten" in tags.values()


def test_a_milestone_opens_an_offer_and_the_caps_refuse_what_breaks_them() -> None:
    engine, state = initialized()
    advancement = capability(engine)
    assert advancement.offers(state) == ()

    ready = at_milestone(state)
    (offer,) = advancement.offers(ready)

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


def test_an_npc_party_members_milestone_writes_their_own_sheet_not_the_players() -> None:
    engine, state = initialized()
    draft = state.draft()
    joined = Relation(kind=PARTY_MEMBER, source=FOE, target=PLAYER_ID, known=True)
    draft.world.relations[joined.id] = joined
    with_companion = draft.committed()

    advancement = capability(engine)
    ready = at_milestone(with_companion)
    offers = {offer.subject_id: offer for offer in advancement.offers(ready)}
    assert set(offers) == {PLAYER_ID, FOE}

    grow_mara = Milestone(
        change="skill", tag="Reads Old Stonework", why="she has read enough of it now"
    )
    draft = ready.draft()
    facts = advancement.resolve(draft, offers[FOE], grow_mara, Random(0))
    grown = draft.committed()

    sheets = grown.mechanics_as(Mechanics).sheets
    assert sheets[FOE].skills[-1] == "Reads Old Stonework"
    assert sheets[PLAYER_ID].skills == ready.mechanics_as(Mechanics).sheets[PLAYER_ID].skills
    assert [fact.kind for fact in facts] == ["skill_gained", "counter_changed"]


def test_an_actor_seeded_after_a_milestone_is_not_owed_the_ones_they_missed() -> None:
    engine, state = initialized()
    ready = at_milestone(state)
    draft = ready.draft()
    newcomer = Entity(
        id=EntityId("newcomer"),
        kind="actor",
        name="A Newcomer",
        brief="Falls in beside Kael.",
        known=True,
        parent_id=draft.player_location,
    )
    _ = draft.add(newcomer)
    engine.seed(draft, newcomer, Random(0))
    joined = Relation(kind=PARTY_MEMBER, source=newcomer.id, target=PLAYER_ID, known=True)
    draft.world.relations[joined.id] = joined
    walked_in = draft.committed()

    engine.validate(walked_in)
    offered = {offer.subject_id for offer in capability(engine).offers(walked_in)}
    assert offered == {PLAYER_ID}


def test_the_one_roll_is_worked_through_in_the_directors_instructions() -> None:
    """A roll without an example teaches the model nothing: coverage is asserted, not hoped."""
    engine, _ = initialized()

    assert engine.director_instructions.count('"name": "question"') == 1
    # Rendered from the model, so what the prompt promises is what a retry would enforce.
    assert "`question` — A closed dramatic question" in engine.director_instructions
    assert "`leverage` (list of at most 3; default [])" in engine.director_instructions


def test_a_hook_reaches_the_engine_s_own_effects() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.world.hooks = (
        Hook(
            id="strain",
            match=HookMatch(kind="entity_discovered"),
            effects=(
                {
                    "op": "counter-change",
                    "mode": "adjust",
                    "entity_id": "player",
                    "counter": "luck",
                    "amount": -1,
                    "why": "the strain of it",
                },
            ),
        ),
    )

    fired = fire_hooks(
        draft,
        [Fact(source=CORE, kind="entity_discovered", trace="the map is found")],
        engine.apply_effect,
    )

    assert [fact.kind for fact in fired] == ["hook_fired", "counter_changed"]
    assert draft.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current == LUCK_MAX - 1


def _refusal(engine: Engine, state: GameState, plan: DirectorPlan) -> str:
    refused = engine.check_beat(state, plan)
    assert refused is not None
    return refused
