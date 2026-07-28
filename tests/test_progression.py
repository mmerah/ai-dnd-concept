"""Levelling and the 5e procedures it unblocks.

The four things worth pinning: a level record is a cumulative snapshot so a level-up is a *diff*;
the decisions a level asks for must be answered exactly; a to-hit or a save comes from the archetype
for a monster and from progression for the player; and none of it needs a pack behind it."""

from collections.abc import Sequence
from random import Random

import pytest
from support import new_game, ruleset, sheet

from aidm.content import ContentRef
from aidm.content.records import BonusOption, ProgressionChoice
from aidm.domain.models import (
    PLAYER_ID,
    ActorEntity,
    Attack,
    Damage,
    Decisions,
    EntityId,
    GameState,
    ItemEntity,
    LeveledUp,
    Origin,
    RollSave,
    updated,
)
from aidm.domain.reducer import apply
from aidm.engine import bestiary, procedures, progression, rules
from aidm.engine.resolve import resolve
from aidm.engine.ruleset import CharacterProfile, LevelProfile, ProgressionRules

RULES = ruleset()
SHEET = sheet()


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


class SmallRules:
    """A whole ruleset, hand-written. A synthetic `Library` could not be written this small — it
    would mean cross-consistent records across classes, levels, features, traits and proficiencies —
    so before the profiles, testing a levelling edge case meant finding an SRD class showing it."""

    def character(self, origin: Origin) -> CharacterProfile:
        return CharacterProfile(hit_die=8, saving_throws=("wisdom",), proficiencies=("cooking",))

    def level(self, origin: Origin, level: int) -> LevelProfile:
        """Every fourth level improves a score, and no level offers anything else."""
        return LevelProfile(prof_bonus=2 + (level - 1) // 4, improvements=int(level % 4 == 0))


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
    """Clamping would spend a permanent choice on nothing: 5e caps a score at 20, so the pick is
    illegal and the player must be told rather than silently charged for it."""
    at_three = levelled(new_game("whispering_vault"), 3)
    player = at_three.player
    maxed = updated(player.stats, attributes=updated(player.stats.attributes, strength=20))
    with pytest.raises(ValueError, match="no ability may exceed 20"):
        progression.advance(
            updated(player, stats=maxed),
            {"ability-scores-4": ("strength", "strength")},
            RULES,
            Random(1),
        )


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


def armed(state: GameState) -> GameState:
    """The player holding a longsword, with a goblin standing where they are."""
    goblin = bestiary.statted(
        ActorEntity(
            id=EntityId("goblin"),
            name="a goblin",
            brief="Small and mean.",
            known=True,
            location_id=state.player.location_id,
            ref=ref("monsters", "goblin"),
        ),
        RULES,
    )
    assert isinstance(goblin, ActorEntity)
    sword = ItemEntity(
        id=EntityId("sword"),
        name="a notched longsword",
        brief="Old steel.",
        known=True,
        ref=ref("weapons", "longsword"),
        container_id=PLAYER_ID,
    )
    entities = {**state.world.entities, goblin.id: goblin, sword.id: sword}
    return updated(state, world=updated(state.world, entities=entities))


def test_a_to_hit_comes_from_the_record_for_a_monster_and_from_progression_for_the_player() -> None:
    """The whole reason `attack` waited for R7: a goblin's +4 and `1d6+2` are on its record, and
    Kael's +2 is a proficiency bonus he had no way of knowing before a class and a level."""
    state = armed(new_game("whispering_vault"))
    goblin = state.world.entities[EntityId("goblin")]
    assert isinstance(goblin, ActorEntity)
    assert procedures.swing(state, goblin, "scimitar", RULES).to_hit == 4
    mine = procedures.swing(state, state.player, "a notched longsword", RULES)
    assert (mine.name, mine.to_hit, mine.damage) == ("a notched longsword", 2, "1d8")
    with pytest.raises(ValueError, match="no attack called"):
        procedures.swing(state, goblin, "Vorpal Sneeze", RULES)


def test_a_hit_deals_the_weapon_s_damage_and_a_miss_deals_nothing() -> None:
    """One proposal, one chain: the Director never gets to decide that a blow landed. Omitting
    `target_id` means the player, as it does everywhere else — no role is shown their id, so a
    required one would make "the goblin swings at you" inexpressible."""
    state = armed(new_game("whispering_vault"))
    swung = Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))
    hit = resolve([swung], state, Random(0), RULES)  # d20 -> 13, +4 = 17 vs ac 10
    assert [e.type for e in hit] == ["attack_rolled", "dice_rolled", "hp_changed"]
    assert hit[0].summary.endswith("13 -> 17 vs ac 10: HIT")
    miss = resolve([swung], state, Random(2), RULES)  # d20 -> 2, +4 = 6
    assert [e.type for e in miss] == ["attack_rolled"]
    assert miss[0].summary.endswith("2 -> 6 vs ac 10: MISS")
    with pytest.raises(ValueError, match="does not strike at themselves"):
        resolve([Attack(weapon="Scimitar")], state, Random(0), RULES)


def test_a_save_uses_the_record_s_bonus_or_the_player_s_proficiency() -> None:
    """A lich's +10 constitution save is absolute on its record; the player's is the ability
    modifier plus the proficiency bonus, on the saves their class is good at and nowhere else."""
    state = new_game("whispering_vault")
    player = state.player
    assert player.progression is not None
    scores = player.stats.attributes
    assert rules.save_bonus(player, "constitution") == rules.modifier(scores, "constitution") + 2
    assert rules.save_bonus(player, "wisdom") == rules.modifier(scores, "wisdom")

    lich = RULES.archetype(ref("monsters", "lich"))
    assert lich is not None
    stats = lich.stats
    undead = updated(player, stats=stats, progression=None)
    assert rules.save_bonus(undead, "constitution") == 10
    assert rules.save_bonus(undead, "strength") == rules.modifier(stats.attributes, "strength")


def test_a_save_selects_its_branch_like_a_check_does() -> None:
    state = armed(new_game("whispering_vault"))
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=EntityId("goblin"),
        on_failure=[Attack(weapon="Scimitar", attacker_id=EntityId("goblin"))],
    )
    events = resolve([gas], state, Random(0), RULES)
    assert events[0].summary == "a goblin dexterity save: 13 -> 15 vs DC 25: FAILURE"
    assert [e.type for e in events[1:]] == ["attack_rolled", "dice_rolled", "hp_changed"]


def test_a_save_on_someone_unseen_reveals_them_exactly_once() -> None:
    """The branch folds against the state the reveal produced, so the Narrator is not told twice
    that the player just noticed the same actor."""
    state = armed(new_game("whispering_vault"))
    goblin = state.world.entities[EntityId("goblin")]
    hidden = {**state.world.entities, goblin.id: updated(goblin, known=False)}
    unseen = updated(state, world=updated(state.world, entities=hidden))
    gas = RollSave(
        ability="dexterity",
        dc=25,
        target_id=goblin.id,
        on_failure=[Damage(amount=1, target_id=goblin.id)],
    )
    events = resolve([gas], unseen, Random(0), RULES)
    assert [e.type for e in events] == ["entity_discovered", "dc_rolled", "hp_changed"]
