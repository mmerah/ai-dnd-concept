from collections.abc import Sequence
from random import Random

import pytest
from support import new_game, ruleset, sheet

from aidm.agents import views
from aidm.agents.context import Scene
from aidm.content.library import ContentMiss
from aidm.content.records.base import ContentRef
from aidm.content.records.character import BonusOption, ProgressionChoice
from aidm.domain.models.base import EntityId
from aidm.domain.models.consequences import (
    LevelUp,
    Rest,
    UseFeature,
)
from aidm.domain.models.entities import ActorEntity
from aidm.domain.models.events import LeveledUp
from aidm.domain.models.progression import (
    Decisions,
    FeatureResourceState,
    Origin,
)
from aidm.domain.models.state import GameState
from aidm.domain.reducer import apply
from aidm.engine import features, progression, rules
from aidm.engine.resolve import resolve
from aidm.engine.ruleset import CharacterProfile, FeatureProfile, LevelProfile, ProgressionRules
from aidm.utils.models import Attributes, updated

RULES = ruleset()
SHEET = sheet()
SECOND_WIND = "srd-2014/features/second-wind"
ACTION_SURGE = "srd-2014/features/action-surge-1-use"


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def answers(choices: Sequence[ProgressionChoice]) -> Decisions:
    """Answer every choice with as many distinct options as it asks for, repeating the first only
    where a choice allows it."""
    return {
        choice.id: tuple(option.key for option in choice.options[: choice.choose])
        if choice.distinct
        else (choice.options[0].key,) * choice.choose
        for choice in choices
    }


def first_of(state: GameState, level: int) -> Decisions:
    current = state.player.progression
    assert current is not None
    return answers(progression.pending(current.origin, level, RULES))


def levelled(state: GameState, to: int) -> GameState:
    """Advance one level at a time, answering each level's choices with its first option."""
    current = state.player.progression
    assert current is not None
    for level in range(current.level + 1, to + 1):
        events = progression.advance(state.player, first_of(state, level), RULES, Random(1))
        state = apply(state, events)
    return state


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
    state = new_game("whispering_vault")
    assert [c.id for c in progression.pending(SHEET.origin, 4, RULES)] == ["ability-scores-4"]
    assert progression.pending(SHEET.origin, 5, RULES) == []
    at_five = levelled(state, 5)
    player = at_five.player
    assert player.progression is not None
    assert player.progression.level == 5 and player.progression.prof_bonus == 3
    # Two picks of +1 on one score is the "+2 to one ability" wording — the one repeatable choice.
    raised = player.stats.attributes.strength - state.player.stats.attributes.strength
    assert raised == 2


def test_a_level_preview_lists_every_level_two_gain_before_advancing() -> None:
    preview = progression.preview(new_game("whispering_vault").player, RULES)
    benefits = preview.benefits
    assert benefits.level == 2
    assert benefits.hit_die == 10
    assert benefits.prof_bonus_before == benefits.prof_bonus_after == 2
    assert benefits.spell_slot_changes == ()
    assert [feature.ref.index for feature in benefits.features] == ["action-surge-1-use"]
    assert preview.choices == ()


def test_the_confirmed_plan_contains_the_selected_subclass_grants() -> None:
    state = levelled(new_game("whispering_vault"), 2)
    decisions = first_of(state, 3)
    plan = progression.plan(state.player, decisions, RULES)
    assert [feature.ref.index for feature in plan.benefits.features] == ["improved-critical"]
    assert plan.selections[0].labels == ("Champion",)

    events = progression.advance(state.player, decisions, RULES, Random(1))
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
    at_three = levelled(new_game("whispering_vault"), 3)
    assert at_three.player.progression is not None
    chosen = at_three.player.progression.origin
    assert chosen.subclass_ref == ref("subclasses", "champion")
    # Chosen once and never again, at the level that offered it or any later one.
    assert progression.pending(chosen, 3, RULES) == []
    assert [c.id for c in progression.pending(chosen, 4, RULES)] == ["ability-scores-4"]


def test_an_ability_score_improvement_may_spend_both_picks_on_one_score() -> None:
    (choice,) = progression.pending(SHEET.origin, 4, RULES)
    assert choice.choose == 2 and not choice.distinct
    assert all(isinstance(o, BonusOption) for o in choice.options)


def test_an_improvement_past_twenty_is_refused_rather_than_clamped() -> None:
    at_three = levelled(new_game("whispering_vault"), 3)
    player = at_three.player
    maxed = updated(player.stats, attributes=updated(player.stats.attributes, strength=20))
    actor = updated(player, stats=maxed)
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
    player = levelled(new_game("whispering_vault"), 3).player
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
    player = levelled(new_game("whispering_vault"), 9).player
    (choice,) = progression.preview(player, RULES).choices
    assert choice.id == "additional-fighting-style-subfeature"
    assert "fighter-fighting-style-defense" not in {option.key for option in choice.options}


def test_spell_slot_changes_show_pact_magic_moving_to_a_new_slot_level() -> None:
    player = new_game("whispering_vault").player
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
        spell_slots={1: 2},
    )
    changes = progression.preview(updated(player, progression=warlock), RULES).benefits
    assert [
        (change.spell_level, change.before, change.after) for change in changes.spell_slot_changes
    ] == [(1, 2, 0), (2, 0, 2)]


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
    state = new_game("whispering_vault")
    mara = state.world.entities[EntityId("mara")]
    assert isinstance(mara, ActorEntity)
    levelled_npc = updated(mara, progression=state.player.progression)
    entities = {**state.world.entities, mara.id: levelled_npc}
    with pytest.raises(ValueError, match="only the player may have progression"):
        updated(state, world=updated(state.world, entities=entities))


def test_levelling_rolls_the_hit_die_where_the_trace_can_see_it() -> None:
    state = new_game("whispering_vault")
    rolled, gained = progression.advance(state.player, {}, RULES, Random(1))
    assert isinstance(gained, LeveledUp)
    assert rolled.summary.startswith("rolled 1d10:")
    after = apply(state, [rolled, gained]).player
    assert after.stats.max_hp - state.player.stats.max_hp == gained.advancement.hp_gain
    assert after.stats.hp == after.stats.max_hp


def test_fighter_features_are_owned_spent_and_recharged() -> None:
    state = levelled(new_game("whispering_vault"), 2)
    progression_state = state.player.progression
    assert progression_state is not None
    assert [feature.index for feature in progression_state.features] == [
        "second-wind",
        "fighter-fighting-style-defense",
        "action-surge-1-use",
    ]
    assert {
        key: resource.remaining for key, resource in progression_state.feature_resources.items()
    } == {SECOND_WIND: 1, ACTION_SURGE: 1}
    shown = views.character(Scene.of(state), RULES)
    assert "Fighting Style: Defense[id=srd-2014/features/fighter-fighting-style-defense]" in shown
    assert (
        f"Second Wind[id={SECOND_WIND}] "
        "[engine-resolved bonus_action — 1/1 uses — short rest — usable]"
    ) in shown
    assert (
        f"Action Surge (1 use)[id={ACTION_SURGE}] "
        "[description-guided special — 1/1 uses — short rest — usable]"
    ) in shown

    player = updated(state.player, stats=updated(state.player.stats, hp=1))
    wounded = updated(state, world=state.world.replacing(player))
    events = resolve(
        [UseFeature(feature=SECOND_WIND), UseFeature(feature=ACTION_SURGE)],
        wounded,
        Random(1),
        RULES,
    )
    assert [event.type for event in events] == [
        "feature_used",
        "dice_rolled",
        "hp_changed",
        "feature_used",
        "feature_activated",
    ]
    spent = apply(wounded, events)
    current = spent.player.progression
    assert current is not None
    assert {key: resource.remaining for key, resource in current.feature_resources.items()} == {
        SECOND_WIND: 0,
        ACTION_SURGE: 0,
    }
    assert spent.player.stats.hp == 6
    depleted = views.character(Scene.of(spent), RULES)
    assert f"Second Wind[id={SECOND_WIND}]" in depleted
    assert "0/1 uses — short rest — depleted" in depleted
    with pytest.raises(ValueError, match="0 uses left"):
        resolve([UseFeature(feature=SECOND_WIND)], spent, Random(1), RULES)

    rested = apply(spent, resolve([Rest(rest="short")], spent, Random(1), RULES))
    current = rested.player.progression
    assert current is not None
    assert {key: resource.remaining for key, resource in current.feature_resources.items()} == {
        SECOND_WIND: 1,
        ACTION_SURGE: 1,
    }


def test_a_replacement_requires_the_feature_it_replaces() -> None:
    replacement = features.profile_of(ref("features", "action-surge-2-uses"), RULES)
    with pytest.raises(ValueError, match="replaces features not held"):
        features.acquire(
            (),
            {},
            (replacement,),
            ruleset=RULES,
            class_level=17,
            attributes=SHEET.starting_attributes,
        )


@pytest.mark.parametrize(("remaining", "upgraded"), [(0, 1), (1, 2)])
def test_a_resource_upgrade_preserves_uses_spent(remaining: int, upgraded: int) -> None:
    before = features.profile_of(ref("features", "action-surge-1-use"), RULES)
    after = features.profile_of(ref("features", "action-surge-2-uses"), RULES)
    _, resources = features.acquire(
        (before.ref,),
        {
            ACTION_SURGE: FeatureResourceState(
                remaining=remaining,
                maximum=1,
                recharge="short",
            )
        },
        (after,),
        ruleset=RULES,
        class_level=17,
        attributes=Attributes(),
    )
    upgraded_resource = resources["srd-2014/features/action-surge-2-uses"]
    assert (upgraded_resource.remaining, upgraded_resource.maximum) == (upgraded, 2)


def test_shared_and_scaled_resources_need_no_class_specific_engine_rules() -> None:
    ki = features.profile_of(ref("features", "ki"), RULES)
    flurry = features.profile_of(ref("features", "flurry-of-blows"), RULES)
    inspiration = features.profile_of(ref("features", "bardic-inspiration-d6"), RULES)
    lay_on_hands = features.profile_of(ref("features", "lay-on-hands"), RULES)

    _, monk_resources = features.acquire(
        (), {}, (ki, flurry), ruleset=RULES, class_level=5, attributes=Attributes()
    )
    assert {key: resource.maximum for key, resource in monk_resources.items()} == {
        "srd-2014/features/ki": 5
    }
    state = new_game("whispering_vault")
    current = state.player.progression
    assert current is not None
    monk = updated(
        current,
        level=5,
        features=(ki.ref, flurry.ref),
        feature_resources=monk_resources,
    )
    player = updated(state.player, progression=monk)
    monk_state = updated(state, world=state.world.replacing(player))
    spent = apply(
        monk_state,
        resolve(
            [UseFeature(feature="srd-2014/features/flurry-of-blows")],
            monk_state,
            Random(1),
            RULES,
        ),
    )
    assert spent.player.progression is not None
    assert spent.player.progression.feature_resources["srd-2014/features/ki"].remaining == 4
    # The counter is named after the feature that owns it, not whichever feature spent from it.
    (rested,) = resolve([Rest(rest="short")], spent, Random(1), RULES)
    assert rested.summary == "completed a short rest; recharged Ki"
    assert apply(spent, [rested]).player.progression == monk

    _, bard_resources = features.acquire(
        (), {}, (inspiration,), ruleset=RULES, class_level=1, attributes=Attributes(charisma=16)
    )
    assert bard_resources["srd-2014/features/bardic-inspiration-d6"].maximum == 3

    _, paladin_resources = features.acquire(
        (), {}, (lay_on_hands,), ruleset=RULES, class_level=5, attributes=Attributes()
    )
    assert paladin_resources["srd-2014/features/lay-on-hands"].maximum == 25
    paladin = updated(
        current,
        level=5,
        features=(lay_on_hands.ref,),
        feature_resources=paladin_resources,
    )
    player = updated(state.player, progression=paladin)
    paladin_state = updated(state, world=state.world.replacing(player))
    spent = apply(
        paladin_state,
        resolve(
            [UseFeature(feature="srd-2014/features/lay-on-hands", amount=7)],
            paladin_state,
            Random(1),
            RULES,
        ),
    )
    assert spent.player.progression is not None
    resource = spent.player.progression.feature_resources["srd-2014/features/lay-on-hands"]
    assert resource.remaining == 18


def test_the_directors_level_up_consequence_unlocks_the_players_level_up() -> None:
    state = new_game("whispering_vault")
    events = resolve([LevelUp()], state, Random(1), RULES)
    assert [event.type for event in events] == ["level_up_available"]
    offered = apply(state, events)
    assert offered.player.progression is not None
    assert offered.player.progression.level == 1
    assert offered.player.progression.level_up_available
    assert resolve([LevelUp()], offered, Random(1), RULES) == []


def test_the_player_answers_choices_after_the_director_awards_a_level() -> None:
    state = levelled(new_game("whispering_vault"), 2)
    assert "not awarded" in views.level_up_status(Scene.of(state))
    state = apply(state, resolve([LevelUp()], state, Random(1), RULES))
    assert "waiting for the player" in views.level_up_status(Scene.of(state))

    decisions = first_of(state, 3)
    events = progression.advance(state.player, decisions, RULES, Random(1))
    after = apply(state, events).player
    assert after.progression is not None
    assert after.progression.level == 3
    assert after.progression.origin.subclass_ref == ref("subclasses", "champion")
    assert not after.progression.level_up_available
