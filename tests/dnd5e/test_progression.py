from collections.abc import Sequence
from random import Random

import pytest
from fivee_progression_support import RULES, SHEET, answers, levelled, next_of, ref, started
from fivee_test_support import new_game, player_of, with_actor

from aidm.domain.base import EntityId
from aidm.domain.state import GameState
from aidm.utils.models import updated
from aidm_5e.content.library import ContentMiss
from aidm_5e.content.records.base import ContentRef
from aidm_5e.content.records.character import BonusOption, ProgressionChoice
from aidm_5e.domain.models.consequences import (
    Cast,
    Consequence,
    Rest,
)
from aidm_5e.domain.models.events import LeveledUp
from aidm_5e.domain.models.progression import (
    MAX_LEVEL,
    Decisions,
    Origin,
    ResourceState,
)
from aidm_5e.domain.reducer import apply
from aidm_5e.engine import progression, rules
from aidm_5e.engine.resolve import resolve
from aidm_5e.engine.ruleset import CharacterProfile, FeatureProfile, LevelProfile, ProgressionRules
from aidm_5e.models import Dnd5eActor
from aidm_5e.state import actor_of


def test_a_sheet_becomes_a_legal_level_one_character() -> None:
    """Hit points are the hit die plus the constitution modifier, and a race's fixed bonuses are
    applied to the sheet's base scores — a half-elf's +2 charisma on top of the rolled 10."""
    start = progression.first_level(SHEET, RULES)
    assert start.progression.level == 1 and start.progression.prof_bonus == 2
    assert start.attributes.charisma == SHEET.starting_attributes.charisma + 2
    assert start.hp_gain == 10 + rules.modifier(start.attributes, "constitution")
    assert start.progression.saving_throws == ("strength", "constitution")


def test_a_decision_must_answer_every_pending_choice_and_nothing_else() -> None:
    """The integrity boundary: a level half-decided is not a level, and an option nobody offered is
    how a character would acquire a proficiency the pack never gave them."""
    answered = answers(progression.pending(SHEET.origin, 1, RULES))
    with pytest.raises(ValueError, match="do not answer"):
        progression.first_level(updated(SHEET, decisions={}), RULES)
    with pytest.raises(ValueError, match="does not offer"):
        outside = {**answered, "fighter-proficiency-1": ("skill-arcana", "skill-athletics")}
        progression.first_level(updated(SHEET, decisions=outside), RULES)
    with pytest.raises(ValueError, match="needs 2 picks"):
        short = {**answered, "fighter-proficiency-1": ("skill-athletics",)}
        progression.first_level(updated(SHEET, decisions=short), RULES)
    with pytest.raises(ValueError, match="may not repeat"):
        twice = {**answered, "fighter-proficiency-1": ("skill-athletics", "skill-athletics")}
        progression.first_level(updated(SHEET, decisions=twice), RULES)


def test_a_level_up_is_the_diff_of_two_records_not_the_record() -> None:
    """`ability_score_bonuses` is a running total: 0,0,0,1,1 over Fighter 1-5. Reading the record
    and applying it would hand out a second improvement at level 5, and a fifth by level 8."""
    state = new_game("whispering_vault_5e")
    assert [c.id for c in progression.pending(SHEET.origin, 4, RULES)] == ["ability-scores-4"]
    assert progression.pending(SHEET.origin, 5, RULES) == []
    at_five = levelled(state, 5)
    player = player_of(at_five)
    reached = player.progression
    assert reached is not None
    assert reached.level == 5 and reached.prof_bonus == 3
    # Two picks of +1 on one score is the "+2 to one ability" wording — the one repeatable choice.
    raised = player.stats.attributes.strength - player_of(state).stats.attributes.strength
    assert raised == 2


def test_a_level_preview_lists_every_level_two_gain_before_advancing() -> None:
    preview = progression.preview(player_of(new_game("whispering_vault_5e")), RULES)
    benefits = preview.benefits
    assert benefits.level == 2
    assert benefits.hit_die == 10
    assert benefits.prof_bonus_before == benefits.prof_bonus_after == 2
    assert benefits.spell_slot_changes == ()
    assert [feature.ref.index for feature in benefits.features] == ["action-surge-1-use"]
    assert preview.choices == ()


def test_the_confirmed_plan_contains_the_selected_subclass_grants() -> None:
    state = levelled(new_game("whispering_vault_5e"), 2)
    decisions = next_of(state)
    plan = progression.plan(player_of(state), decisions, RULES)
    assert [feature.ref.index for feature in plan.benefits.features] == ["improved-critical"]
    assert plan.selections[0].labels == ("Champion",)

    events = progression.advance(player_of(state), decisions, RULES, Random(1))
    gained = events[-1]
    assert isinstance(gained, LeveledUp)
    assert gained.advancement.progression == plan.progression
    assert gained.advancement.attributes == plan.attributes


class SmallRules:
    """A whole ruleset, hand-written. A synthetic `Content` could not be written this small — it
    would mean cross-consistent records across classes, levels, features, traits and proficiencies —
    so before the profiles, testing a levelling edge case meant finding an SRD class showing it."""

    def character(self, origin: Origin) -> CharacterProfile:
        return CharacterProfile(hit_die=8, saving_throws=("wisdom",), proficiencies=("cooking",))

    def level(self, origin: Origin, level: int) -> LevelProfile:
        """Every fourth level improves a score, and no level offers anything else."""
        return LevelProfile(prof_bonus=2 + (level - 1) // 4, improvements=int(level % 4 == 0))

    def feature(self, ref: ContentRef) -> FeatureProfile | ContentMiss:
        return ContentMiss(ref=ref, reason="unknown_pack")


def test_a_synthetic_ruleset_needs_no_pack_behind_it() -> None:
    """The seam the profiles bought: `engine/` asks two questions, so a test can answer both."""
    small: ProgressionRules = SmallRules()
    plain = updated(SHEET, decisions={})  # this ruleset asks nothing, so nothing may be answered
    start = progression.first_level(plain, small)
    assert start.progression.saving_throws == ("wisdom",)
    assert start.progression.proficiencies == ("cooking",)
    assert start.hp_gain == 8 + rules.modifier(start.attributes, "constitution")
    assert [c.id for c in progression.pending(plain.origin, 8, small)] == ["ability-scores-8"]
    assert progression.pending(plain.origin, 7, small) == []


def test_a_subclass_is_chosen_off_the_class_at_the_level_it_first_grants_something() -> None:
    """The `martial-archetype` feature carries an English sentence and no options at all, so
    `ClassRecord.subclass` is the only thing that could drive the choice."""
    assert [c.id for c in progression.pending(SHEET.origin, 3, RULES)] == ["fighter-subclass"]
    at_three = levelled(new_game("whispering_vault_5e"), 3)
    reached = player_of(at_three).progression
    assert reached is not None
    chosen = reached.origin
    assert chosen.subclass_ref == ref("subclasses", "champion")
    # Chosen once and never again, at the level that offered it or any later one.
    assert progression.pending(chosen, 3, RULES) == []
    assert [c.id for c in progression.pending(chosen, 4, RULES)] == ["ability-scores-4"]


def test_an_ability_score_improvement_may_spend_both_picks_on_one_score() -> None:
    (choice,) = progression.pending(SHEET.origin, 4, RULES)
    assert choice.choose == 2 and not choice.distinct
    assert all(isinstance(o, BonusOption) for o in choice.options)


def test_an_improvement_past_twenty_is_refused_rather_than_clamped() -> None:
    at_three = levelled(new_game("whispering_vault_5e"), 3)
    player = player_of(at_three)
    maxed = updated(player.stats, attributes=updated(player.stats.attributes, strength=20))
    actor = Dnd5eActor(entity=player.entity, state=updated(player.state, stats=maxed))
    (choice,) = progression.preview(actor, RULES).choices
    assert "strength" not in {option.key for option in choice.options}
    with pytest.raises(ValueError, match="does not offer 'strength'"):
        progression.advance(
            actor,
            {"ability-scores-4": ("strength", "strength")},
            RULES,
            Random(1),
        )


def test_a_constitution_increase_adds_hp_for_every_existing_level() -> None:
    player = player_of(levelled(new_game("whispering_vault_5e"), 3))
    decisions = {"ability-scores-4": ("constitution", "constitution")}
    plan = progression.plan(player, decisions, RULES)
    assert plan.benefits.retroactive_hp_gain == 3

    con_events = progression.advance(player, decisions, RULES, Random(1))
    strength_events = progression.advance(
        player,
        {"ability-scores-4": ("strength", "strength")},
        RULES,
        Random(1),
    )
    con_level = con_events[-1]
    strength_level = strength_events[-1]
    assert isinstance(con_level, LeveledUp) and isinstance(strength_level, LeveledUp)
    assert con_level.advancement.hp_gain == strength_level.advancement.hp_gain + 4


def test_a_level_choice_does_not_offer_a_feature_already_held() -> None:
    player = player_of(levelled(new_game("whispering_vault_5e"), 9))
    (choice,) = progression.preview(player, RULES).choices
    assert choice.id == "additional-fighting-style-subfeature"
    assert "fighter-fighting-style-defense" not in {option.key for option in choice.options}


def test_spell_slot_changes_show_pact_magic_moving_to_a_new_slot_level() -> None:
    player = player_of(new_game("whispering_vault_5e"))
    current = player.progression
    assert current is not None
    warlock = updated(
        current,
        origin=updated(
            current.origin,
            class_ref=ref("classes", "warlock"),
            subclass_ref=ref("subclasses", "fiend"),
        ),
        level=2,
        spell_slots={1: ResourceState(remaining=2, maximum=2, recharge="short")},
    )
    caster = Dnd5eActor(entity=player.entity, state=updated(player.state, progression=warlock))
    changes = progression.preview(caster, RULES).benefits
    assert [
        (change.slot_level, change.before, change.after) for change in changes.spell_slot_changes
    ] == [(1, 2, 0), (2, 0, 2)]


def test_a_known_caster_picks_its_repertoire_at_level_up_and_a_prepared_one_does_not() -> None:
    """`spells_known` is a cumulative total for a known caster and null for a prepared one, which is
    the only thing in the pack that tells the two kinds apart. A bard picks four spells at level 1
    and one more at level 2; a wizard picks cantrips only, because preparation is not modelled."""
    bard = player_of(started("bard", new_game("whispering_vault_5e"))).progression
    assert bard is not None
    assert len(bard.chosen_spells) == 2 + 4  # two cantrips known, four spells known
    at_two = player_of(levelled(started("bard", new_game("whispering_vault_5e")), 2)).progression
    assert at_two is not None and len(at_two.chosen_spells) == len(bard.chosen_spells) + 1

    wizard = player_of(started("wizard", new_game("whispering_vault_5e"))).progression
    assert wizard is not None
    assert [c.id for c in progression.pending(wizard.origin, 1, RULES)] == [
        "wizard-proficiency-1",
        "wizard-cantrips-1",
    ]
    cantrips = ["acid-splash", "chill-touch", "dancing-lights"]
    assert [spell.index for spell in wizard.chosen_spells] == cantrips


def test_spell_slots_are_spent_recharged_by_the_right_rest_and_spent_again() -> None:
    """Pact Magic flows through the same `spell_slots` field as every other class and returns on a
    short rest, so the recharge has to travel with the slots rather than be assumed."""
    comprehend = Cast(spell="srd-2014/spells/comprehend-languages", slot_level=1)

    def remaining(state: GameState) -> dict[int, int]:
        current = player_of(state).progression
        assert current is not None
        return {level: slot.remaining for level, slot in current.spell_slots.items()}

    def resolved(state: GameState, *mechanics: Consequence) -> GameState:
        return apply(state, resolve(mechanics, state, Random(1), RULES))

    wizard = started("wizard", new_game("whispering_vault_5e"))
    assert remaining(wizard) == {1: 2}
    spent = resolved(wizard, comprehend, comprehend)
    assert remaining(spent) == {1: 0}
    with pytest.raises(ValueError, match="no level 1 spell slot remains; finish a long rest"):
        resolve([comprehend], spent, Random(1), RULES)
    assert resolved(spent, Rest(rest="short")) == spent
    rested = resolved(spent, Rest(rest="long"))
    assert remaining(rested) == {1: 2}
    assert remaining(resolved(rested, comprehend)) == {1: 1}

    warlock = started("warlock", new_game("whispering_vault_5e"))
    pact = resolved(warlock, comprehend)
    assert remaining(pact) == {1: 0}
    assert remaining(resolved(pact, Rest(rest="short"))) == {1: 1}


@pytest.mark.parametrize(
    ("klass", "known", "slots", "recharge"),
    [
        ("bard", 22 + 4, {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1}, "long"),
        ("warlock", 15 + 4, {5: 4}, "short"),
    ],
)
def test_a_known_caster_reaches_level_twenty_with_the_srds_slots_and_repertoire(
    klass: str, known: int, slots: dict[int, int], recharge: str
) -> None:
    """The picks accumulate and an already-held spell leaves the options, so the pool has to stay
    deep enough for twenty levels. Pact Magic ends as one pool of four level-5 slots that a short
    rest returns, which is why the recharge travels with the slots."""
    state = started(klass, new_game("whispering_vault_5e"))
    for level in range(2, MAX_LEVEL + 1):
        spread = _spread(progression.preview(player_of(state), RULES).choices, level)
        state = apply(state, progression.advance(player_of(state), spread, RULES, Random(1)))
    current = player_of(state).progression
    assert current is not None and current.level == MAX_LEVEL
    assert len(current.chosen_spells) == known
    assert {n: slot.maximum for n, slot in current.spell_slots.items()} == slots
    assert {slot.recharge for slot in current.spell_slots.values()} == {recharge}


def _spread(choices: Sequence[ProgressionChoice], offset: int) -> Decisions:
    """Cycle a repeatable choice, so twenty levels of improvements do not cap one ability at 20."""
    return {
        choice.id: tuple(option.key for option in choice.options[: choice.choose])
        if choice.distinct
        else tuple(
            choice.options[(offset + n) % len(choice.options)].key for n in range(choice.choose)
        )
        for choice in choices
    }


def test_expertise_may_only_double_a_proficiency_the_character_already_holds() -> None:
    """A rogue's expertise choice offers all 18 skills whether they have them or not. Treating a
    pick as a grant would hand out a proficiency the pack never gave them."""
    rogue = updated(SHEET, origin=Origin(class_ref=ref("classes", "rogue")))
    answered = dict(answers(progression.pending(rogue.origin, 1, RULES)))
    held = answered["rogue-proficiency-1"]
    legal = updated(rogue, decisions={**answered, "rogue-expertise-1-expertise": held[:2]})
    assert progression.first_level(legal, RULES).progression.proficiencies

    unheld = ("skill-arcana", "skill-history")  # never offered by rogue-proficiency-1's first four
    assert not set(unheld) & set(held)
    with pytest.raises(ValueError, match="cannot double a proficiency"):
        progression.first_level(
            updated(rogue, decisions={**answered, "rogue-expertise-1-expertise": unheld}), RULES
        )


def test_a_save_proficiency_is_recorded_once() -> None:
    """A class states its saves twice upstream — as abilities and as `saving-throw-*` records — and
    `saving_throws` is the one `rules.save_bonus` reads."""
    progressed = progression.first_level(SHEET, RULES).progression
    assert progressed.saving_throws == ("strength", "constitution")
    assert not [p for p in progressed.proficiencies if p.startswith("saving-throw")]


def test_only_the_player_may_have_progression() -> None:
    """`LeveledUp` names no target because of this rule; an NPC carrying progression would make the
    event ambiguous."""
    state = new_game("whispering_vault_5e")
    mara = actor_of(state, EntityId("mara"))
    levelled_npc = updated(mara.state, progression=player_of(state).progression)
    with pytest.raises(ValueError, match="only the player may have progression"):
        with_actor(state, mara.entity, levelled_npc)


def test_levelling_rolls_the_hit_die_where_the_trace_can_see_it() -> None:
    state = new_game("whispering_vault_5e")
    rolled, gained = progression.advance(player_of(state), {}, RULES, Random(1))
    assert isinstance(gained, LeveledUp)
    assert rolled.summary.startswith("rolled 1d10:")
    after = player_of(apply(state, [rolled, gained]))
    assert after.stats.max_hp - player_of(state).stats.max_hp == gained.advancement.hp_gain
    assert after.stats.hp == after.stats.max_hp
