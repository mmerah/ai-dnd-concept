from random import Random

from core_test_support import at_boundary, capability, initialized

from aidm.engines.loader import Engine
from aidm.engines.loner3e.actions import (
    HARM,
    EndAdventure,
    Question,
    defeat_note,
    outcome_for,
    resolve_question,
    twist_note,
    twist_pairing,
)
from aidm.engines.loner3e.advance import AdventureGrowth, Change
from aidm.engines.loner3e.mechanics import LUCK_MAX, TIES_PER_TWIST, Mechanics
from aidm.engines.loner3e.pack import SRD_PACK, twist_table
from aidm.engines.loner3e.rules import Loner3eEngine
from aidm.engines.sheets import SheetBase
from aidm.state.apply import fire_hooks
from aidm.state.base import PLAYER_ID, Counter, Entity, EntityId
from aidm.state.effects import TraitChange
from aidm.state.facts import CORE, Fact
from aidm.state.plan import DirectorBeat
from aidm.state.world import PARTY_MEMBER, GameState, Hook, HookMatch, Relation

TWISTS = twist_table(Loner3eEngine().packs, SRD_PACK)
SURE_FOOTED = TraitChange(mode="add", entity_id=PLAYER_ID, trait_id="sure-footed")
FOE = EntityId("mara")


def _plan(**args: object) -> DirectorBeat:
    return DirectorBeat.model_validate(
        {
            "effects": ({"name": "trait-change", "args": SURE_FOOTED.model_dump()},),
            "roll": {
                "name": "question",
                "args": {
                    "question": "Does he get the seal open before the whispering finds him?",
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
    elsewhere = _plan(actor_id=PLAYER_ID, opponent_id="cloister_rat")
    assert "is not here with the player" in _refusal(engine, state, elsewhere)
    alone = _plan(actor_id=PLAYER_ID, opponent_id=PLAYER_ID)
    assert "their own opposition" in _refusal(engine, state, alone)

    accepted = _plan(actor_id=PLAYER_ID, position="advantage", edge="Reads Old Stonework")
    assert engine.check_beat(state, accepted) is None


def test_an_effect_this_engine_has_not_is_refused_by_naming_every_effect_it_has() -> None:
    """The engine's own union is nested, so the retry names its ops as well as the world's."""
    engine, state = initialized()
    unknown = DirectorBeat.model_validate({"effects": ({"name": "no-such-effect", "args": {}},)})

    refusal = _refusal(engine, state, unknown)

    assert "'reveal'" in refusal
    assert "'restore-luck'" in refusal


def test_the_judged_position_is_what_reaches_the_dice_and_the_record() -> None:
    _, state = initialized()
    action = Question(
        actor_id=PLAYER_ID,
        question="Does he force the seal before the whispering finds him?",
        position="disadvantage",
        edge="Never Walks Away",
    )

    facts = resolve_question(state.draft(), action, Random(1), TWISTS).facts

    (answered,) = [fact for fact in facts if fact.kind == "question_answered"]
    assert (answered.data["position"], answered.data["edge"]) == (
        "disadvantage",
        "Never Walks Away",
    )
    (risk,) = [fact for fact in facts if str(fact.data.get("reason", "")).endswith("risk")]
    assert risk.data["faces"] == [6, 6]


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


def test_an_adventures_end_opens_an_offer_and_the_caps_refuse_what_breaks_them() -> None:
    engine, state = initialized()
    advancement = capability(engine)
    assert advancement.offers(state) == ()

    ready = at_boundary(state)
    (offer,) = advancement.offers(ready)

    legal = AdventureGrowth(
        changes=(Change(kind="skill", tag="Reads a Second Tongue"),),
        why="the old texts finally make sense",
    )
    rewrite = AdventureGrowth(
        changes=(Change(kind="rewrite", tag="Never Walks Away", into="Knows When to Walk Away"),),
        why="the vault taught him the cost",
    )
    unwritten = AdventureGrowth(
        changes=(Change(kind="rewrite", tag="Never Held a Blade", into="Knows When to Walk Away"),),
        why="the vault taught him the cost",
    )

    assert advancement.violation(ready, offer, legal) is None
    assert advancement.violation(ready, offer, rewrite) is None
    assert advancement.violation(ready, offer, unwritten) == (
        "Kael carries no tag 'Never Held a Blade' to rewrite"
    )


def test_an_npc_party_members_growth_writes_their_own_sheet_not_the_players() -> None:
    engine, state = initialized()
    draft = state.draft()
    joined = Relation(kind=PARTY_MEMBER, source=FOE, target=PLAYER_ID, known=True)
    draft.world.relations[joined.id] = joined
    with_companion = draft.committed()

    advancement = capability(engine)
    ready = at_boundary(with_companion)
    offers = {offer.subject_id: offer for offer in advancement.offers(ready)}
    assert set(offers) == {PLAYER_ID, FOE}

    grow_mara = AdventureGrowth(
        changes=(Change(kind="skill", tag="Reads Old Stonework"),),
        why="she has read enough of it now",
    )
    draft = ready.draft()
    facts = advancement.resolve(draft, offers[FOE], grow_mara, Random(0))
    grown = draft.committed()

    sheets = grown.mechanics_as(Mechanics).sheets
    assert sheets[FOE].skills[-1] == "Reads Old Stonework"
    assert sheets[PLAYER_ID].skills == ready.mechanics_as(Mechanics).sheets[PLAYER_ID].skills
    assert [fact.kind for fact in facts] == ["skill_gained", "counter_changed"]


def test_an_actor_seeded_after_an_adventure_is_not_owed_the_growth_they_missed() -> None:
    engine, state = initialized()
    ready = at_boundary(state)
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


def test_end_adventure_gates_the_offer_and_a_second_one_earns_a_second() -> None:
    engine, state = initialized()
    advancement = capability(engine)
    assert advancement.offers(state) == ()

    draft = state.draft()
    engine.apply(draft, EndAdventure())
    once = draft.committed()
    (offer,) = advancement.offers(once)

    change = AdventureGrowth(
        changes=(Change(kind="gear", tag="Waxed Rope"),), why="he never climbs without it now"
    )
    draft = once.draft()
    advancement.resolve(draft, offer, change, Random(0))
    spent = draft.committed()
    assert advancement.offers(spent) == ()

    draft = spent.draft()
    engine.apply(draft, EndAdventure())
    twice = draft.committed()
    assert len(advancement.offers(twice)) == 1


def test_an_adventure_growth_with_three_changes_lands_all_three_on_the_sheet() -> None:
    engine, state = initialized()
    advancement = capability(engine)
    draft = state.draft()
    engine.apply(draft, EndAdventure())
    ready = draft.committed()
    (offer,) = advancement.offers(ready)

    growth = AdventureGrowth(
        changes=(
            Change(kind="skill", tag="Reads Old Stonework"),
            Change(kind="gear", tag="Waxed Rope"),
            Change(kind="frailty", tag="Flinches at the Dark"),
        ),
        why="the vault left its mark on him",
    )
    draft = ready.draft()
    facts = advancement.resolve(draft, offer, growth, Random(0))
    grown = draft.committed()

    sheet = grown.mechanics_as(Mechanics).sheets[PLAYER_ID]
    assert (sheet.skills[-1], sheet.gear[-1], sheet.frailties[-1]) == (
        "Reads Old Stonework",
        "Waxed Rope",
        "Flinches at the Dark",
    )
    assert [fact.kind for fact in facts] == [
        "skill_gained",
        "gear_gained",
        "frailty_gained",
        "counter_changed",
    ]


def test_the_one_roll_is_worked_through_in_the_directors_instructions() -> None:
    """A roll without an example teaches the model nothing: coverage is asserted, not hoped."""
    engine, _ = initialized()

    assert engine.director_instructions.count('"name": "question"') == 1
    # Rendered from the model, so what the prompt promises is what a retry would enforce.
    assert "`question` — A closed dramatic question" in engine.director_instructions
    assert (
        '`position` (one of `advantage`, `neutral`, `disadvantage`; default "neutral")'
        in engine.director_instructions
    )


def test_a_hook_reaches_the_engine_s_own_effects() -> None:
    engine, state = initialized()
    draft = state.draft()
    draft.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current = LUCK_MAX - 2
    draft.world.hooks = (
        Hook(
            id="strain",
            match=HookMatch(kind="entity_discovered"),
            effects=({"name": "restore-luck", "args": {"actor_id": "player"}},),
        ),
    )

    fired = fire_hooks(
        draft,
        [Fact(source=CORE, kind="entity_discovered", trace="the map is found")],
        engine.apply_effect,
    )

    assert [fact.kind for fact in fired] == ["hook_fired", "counter_changed"]
    assert draft.mechanics_as(Mechanics).sheets[PLAYER_ID].luck.current == LUCK_MAX


def test_restoring_luck_that_is_already_full_is_a_quiet_no_op() -> None:
    engine, state = initialized()
    draft = state.draft()

    assert (
        engine.apply_effect(draft, {"name": "restore-luck", "args": {"actor_id": PLAYER_ID}}) == []
    )


def _refusal(engine: Engine[SheetBase], state: GameState, plan: DirectorBeat) -> str:
    refused = engine.check_beat(state, plan)
    assert refused is not None
    return refused
