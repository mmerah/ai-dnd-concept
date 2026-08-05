from random import Random
from typing import cast as as_int

import pytest
from core_test_support import updated
from fivee_progression_support import levelled, started
from fivee_test_support import actor_of, new_game, player_of, ruleset, turn_of, with_actor
from fivee_test_support import content_ref as ref
from pydantic_ai import ModelRetry

from aidm.core import dice
from aidm.core.base import Entity, EntityId
from aidm.core.facts import Fact
from aidm.engines.dnd5e import bestiary, spells
from aidm.engines.dnd5e.state import Dnd5eActorDefinition, Dnd5eState, Progression

RULES = ruleset()
GARGOYLE = EntityId("gargoyle")
GARGOYLE_HP = 52
# Random(0)'s first d20 is 13 and Random(2)'s is 2: against DC 12, a save passes and a save fails.
SAVE_MADE, SAVE_MISSED = 0, 2


def guarded(klass: str, level: int = 1) -> Dnd5eState:
    """A caster of `klass` with a gargoyle to aim at, whose 52 hp make half damage visible."""
    state = levelled(started(klass, new_game()), level)
    gargoyle = Entity(
        id=GARGOYLE,
        kind="actor",
        name="a gargoyle",
        brief="Stone until it is not.",
        known=True,
        parent_id=player_of(state).entity.parent_id,
    )
    authored = Dnd5eActorDefinition(ref=ref("monsters", "gargoyle"))
    return with_actor(
        state,
        gargoyle,
        bestiary.statted_actor(GARGOYLE, authored.model_dump(mode="json"), RULES),
    )


def cast(
    state: Dnd5eState, spell: str, slot_level: int, seed: int = 1
) -> tuple[list[Fact], Dnd5eState]:
    turn = turn_of(state, Random(seed))
    facts = turn.call(
        turn.tools.cast,
        spell=f"srd-2014/spells/{spell}",
        slot_level=slot_level,
        target_id=GARGOYLE,
    )
    return facts, turn.committed()


def rolled(facts: list[Fact]) -> Fact:
    (found,) = [fact for fact in facts if fact.kind == "dice_rolled"]
    return found


def saving_throw(facts: list[Fact]) -> Fact:
    (found,) = [fact for fact in facts if fact.kind == "dc_rolled"]
    return found


def harm(state: Dnd5eState) -> int:
    return GARGOYLE_HP - actor_of(state, GARGOYLE).stats.hp


def hp_changed(facts: list[Fact]) -> Fact:
    (found,) = [fact for fact in facts if fact.kind == "hp_changed"]
    return found


def test_a_save_that_halves_on_success_halves_rather_than_skips() -> None:
    """`on_success: half` is the one save outcome the engine can own, and no dice expression can
    express half of itself, so the roll is emitted and its total halved after the fact."""
    made, missed = guarded("wizard", level=5), guarded("wizard", level=5)
    saved, made_after = cast(made, "fireball", 3, SAVE_MADE)
    failed, missed_after = cast(missed, "fireball", 3, SAVE_MISSED)
    assert saving_throw(saved).data["success"] and not saving_throw(failed).data["success"]
    assert [fact.kind for fact in saved] == [
        "spell_slot_spent",
        "spell_cast",
        "dc_rolled",
        "dice_rolled",
        "hp_changed",
    ]
    assert rolled(saved).data["dice"] == "8d6"
    assert harm(made_after) == as_int(int, rolled(saved).data["total"]) // 2
    assert harm(missed_after) == rolled(failed).data["total"]
    assert hp_changed(saved).trace == "a gargoyle is hurt"


def test_an_attack_spell_rolls_to_hit_and_a_cantrip_scales_off_character_level() -> None:
    """`fire-bolt` carries no `at_slot_level` at all; its damage is `at_character_level`, and those
    steps are 1/5/11/17, so a level 5 wizard throws 2d10 rather than the table's first entry."""
    events, _ = cast(guarded("wizard", level=5), "fire-bolt", 0, seed=0)  # seed 0 rolls a hit
    assert [fact.kind for fact in events] == [
        "spell_cast",  # a cantrip spends no slot
        "attack_rolled",
        "dice_rolled",
        "hp_changed",
    ]
    assert rolled(events).data["dice"] == "2d10"


def test_a_healing_spell_substitutes_the_casters_modifier_before_rolling() -> None:
    """Six SRD spells state `MOD` in their dice and `roll_dice` refuses it by design, so the
    spellcasting modifier has to be folded in first. Kael's wisdom is 14, so a cleric heals +2."""
    cleric = guarded("cleric")
    caster = player_of(cleric)
    wounded = with_actor(
        cleric, caster.entity, updated(caster.state, stats=updated(caster.stats, hp=2))
    )
    turn = turn_of(wounded, Random(1))
    facts = turn.call(turn.tools.cast, spell="srd-2014/spells/cure-wounds", slot_level=1)
    assert rolled(facts).data["dice"] == "1d8 + 2"
    assert player_of(turn.committed()).stats.hp == 2 + as_int(int, rolled(facts).data["total"])


def test_a_negative_modifier_folds_its_sign_rather_than_being_pasted_in() -> None:
    """'+ -1' does not parse, so the substitution recombines the sign instead of replacing text."""
    assert dice.substituted("1d8 + MOD", 2) == "1d8 + 2"
    assert dice.substituted("1d8 + MOD", -1) == "1d8 - 1"
    assert dice.substituted("2d6 + 3", 4) == "2d6 + 3"
    # A leading term carries no sign at all, so there is no correct string to return.
    with pytest.raises(ValueError, match="leading MOD"):
        dice.substituted("MOD + 1d4", -1)


@pytest.mark.parametrize(
    ("spell", "slot_level", "fault"),
    [
        ("cure-wounds", 1, "cannot cast 'cure-wounds'"),  # a cleric spell, not a wizard one
        ("fireball", 2, "level 3; a level 2 slot is too low"),
        ("fire-bolt", 1, "cantrip 'fire-bolt' spends no spell slot"),
        ("fireball", 9, "no level 9 spell slots"),
    ],
)
def test_an_illegal_cast_is_refused_rather_than_resolved(
    spell: str, slot_level: int, fault: str
) -> None:
    with pytest.raises(ModelRetry, match=fault):
        cast(guarded("wizard", level=5), spell, slot_level)


def test_a_class_that_casts_nothing_and_a_spell_aimed_at_its_caster_are_refused() -> None:
    with pytest.raises(ModelRetry, match="class 'fighter' casts no spells"):
        cast(guarded("fighter"), "fireball", 3)
    wizard = guarded("wizard", level=5)
    turn = turn_of(wizard, Random(1))
    with pytest.raises(ModelRetry, match="needs a target other than the caster"):
        turn.call(turn.tools.cast, spell="srd-2014/spells/fireball", slot_level=3)
    # Dancing Lights types no effect to aim, so nothing downstream would read the id.
    with pytest.raises(ModelRetry, match="unknown entity id"):
        turn.call(
            turn.tools.cast,
            spell="srd-2014/spells/dancing-lights",
            slot_level=0,
            target_id=EntityId("nobody"),
        )


def castable(progression: Progression) -> set[str]:
    casting = spells.spellcasting(progression, RULES)
    return {spell.ref.index for spell in spells.repertoire(progression, casting, RULES)}


def test_a_prepared_caster_casts_its_class_list_and_a_known_caster_only_what_it_chose() -> None:
    """The kinds differ in what the pack can record: a wizard's preparation is not modelled, so the
    class list is the gate; a warlock chose its spells at level-up, so those are."""
    wizard = player_of(guarded("wizard", level=5)).progression
    warlock = player_of(guarded("warlock")).progression
    assert wizard is not None and warlock is not None
    prepared = castable(wizard)
    assert "fireball" in prepared and "fireball" not in {s.index for s in wizard.chosen_spells}
    assert "cloudkill" not in prepared  # level 5 grants slots up to level 3, and no further
    assert castable(warlock) == {spell.index for spell in warlock.chosen_spells}
