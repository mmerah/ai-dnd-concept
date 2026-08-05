import pytest
from fivee_test_support import PACK_DIR, pack_format

from aidm.core.packs import Content, ContentRef, LenientRecord, load
from aidm.core.sheet import Sheet
from aidm.engines.dnd5e.content import (
    Amount,
    SpellFacts,
    WeaponFacts,
    spell_of,
    spellcasting_ability,
    weapon_of,
)

LONGSWORD = ContentRef(pack="srd-2014", collection="weapons", index="longsword")
SHORTBOW = ContentRef(pack="srd-2014", collection="weapons", index="shortbow")
DAGGER = ContentRef(pack="srd-2014", collection="weapons", index="dagger")
LANTERN = ContentRef(pack="srd-2014", collection="gear", index="lantern-hooded")
MAGIC_MISSILE = ContentRef(pack="srd-2014", collection="spells", index="magic-missile")
BURNING_HANDS = ContentRef(pack="srd-2014", collection="spells", index="burning-hands")
FIRE_BOLT = ContentRef(pack="srd-2014", collection="spells", index="fire-bolt")
CURE_WOUNDS = ContentRef(pack="srd-2014", collection="spells", index="cure-wounds")
HOLD_PERSON = ContentRef(pack="srd-2014", collection="spells", index="hold-person")
WIZARD = ContentRef(pack="srd-2014", collection="classes", index="wizard")
FIGHTER = ContentRef(pack="srd-2014", collection="classes", index="fighter")


def _content() -> Content:
    return load((PACK_DIR,), pack_format())


def test_weapon_facts_reads_dice_and_tags_off_the_shipped_pack() -> None:
    content = _content()

    longsword = WeaponFacts.from_record(content.require(LONGSWORD, LenientRecord))
    assert longsword is not None
    assert (longsword.damage, longsword.versatile_damage) == ("1d8", "1d10")
    assert longsword.dice(two_handed=False) == "1d8"
    assert longsword.dice(two_handed=True) == "1d10"
    assert (longsword.ranged, longsword.finesse) == (False, False)

    shortbow = WeaponFacts.from_record(content.require(SHORTBOW, LenientRecord))
    assert shortbow is not None
    assert (shortbow.damage, shortbow.ranged) == ("1d6", True)

    dagger = WeaponFacts.from_record(content.require(DAGGER, LenientRecord))
    assert dagger is not None
    assert (dagger.damage, dagger.finesse) == ("1d4", True)

    assert WeaponFacts.from_record(content.require(LANTERN, LenientRecord)) is None


def test_weapon_of_reads_the_first_weapons_ref_on_an_items_sheet() -> None:
    content = _content()
    carried = Sheet(kind="item", refs=(LANTERN, LONGSWORD))

    facts = weapon_of(content, carried)

    assert facts is not None
    assert facts.damage == "1d8"
    assert weapon_of(content, Sheet(kind="item", refs=(LANTERN,))) is None


def test_spell_facts_reads_level_attack_save_and_damage_off_the_shipped_pack() -> None:
    """`damage_at`/`heal_at` pick the base row below the first threshold and the scaled row at
    and above it — by slot for a levelled spell, by caster level for a cantrip."""
    content = _content()

    magic_missile = SpellFacts.from_record(content.require(MAGIC_MISSILE, LenientRecord))
    assert magic_missile is not None
    assert magic_missile.level == 1
    assert (magic_missile.attack, magic_missile.save_ability) == (False, None)
    assert magic_missile.damage_at(1) == Amount(dice="3d4 + 3")
    assert magic_missile.damage_at(2) == Amount(dice="4d4 + 4")

    burning_hands = SpellFacts.from_record(content.require(BURNING_HANDS, LenientRecord))
    assert burning_hands is not None
    assert (burning_hands.save_ability, burning_hands.half_on_save) == ("dexterity", True)
    assert burning_hands.damage_at(1) == Amount(dice="3d6")
    assert burning_hands.damage_at(2) == Amount(dice="4d6")

    fire_bolt = SpellFacts.from_record(content.require(FIRE_BOLT, LenientRecord))
    assert fire_bolt is not None
    assert (fire_bolt.level, fire_bolt.attack) == (None, True)
    assert fire_bolt.damage_at(4) == Amount(dice="1d10")
    assert fire_bolt.damage_at(5) == Amount(dice="2d10")

    cure_wounds = SpellFacts.from_record(content.require(CURE_WOUNDS, LenientRecord))
    assert cure_wounds is not None
    heal = cure_wounds.heal
    assert heal is not None and heal.with_modifier is True
    assert (heal.dice, heal.bonus(2)) == ("1d8", 2)
    heal_at_two = cure_wounds.heal_at(2)
    assert heal_at_two is not None and heal_at_two.dice == "2d8"

    hold_person = SpellFacts.from_record(content.require(HOLD_PERSON, LenientRecord))
    assert hold_person is not None
    assert hold_person.concentration is True
    assert hold_person.half_on_save is False


def test_spell_of_raises_for_a_ref_that_names_no_spell() -> None:
    content = _content()

    with pytest.raises(ValueError, match="names no spell"):
        _ = spell_of(content, str(LONGSWORD))


def test_spellcasting_ability_reads_the_class_record_and_none_for_a_class_that_casts_none() -> None:
    content = _content()

    assert spellcasting_ability(content, Sheet(kind="actor", refs=(WIZARD,))) == "intelligence"
    assert spellcasting_ability(content, Sheet(kind="actor", refs=(FIGHTER,))) is None
