import pytest
from fivee_test_support import PACK_DIR, pack_format

from aidm.engines.dnd5e.records import (
    SpellAmount,
    SpellRecord,
    WeaponRecord,
    spell_of,
    spellcasting_ability,
    weapon_of,
)
from aidm.state.packs import Content, ContentRef, load
from aidm.state.sheet import Sheet

LONGSWORD = ContentRef(pack="srd-2014", collection="weapons", index="longsword")
LANTERN = ContentRef(pack="srd-2014", collection="gear", index="lantern-hooded")
MAGIC_MISSILE = ContentRef(pack="srd-2014", collection="spells", index="magic-missile")
BURNING_HANDS = ContentRef(pack="srd-2014", collection="spells", index="burning-hands")
FIRE_BOLT = ContentRef(pack="srd-2014", collection="spells", index="fire-bolt")
CURE_WOUNDS = ContentRef(pack="srd-2014", collection="spells", index="cure-wounds")
WIZARD = ContentRef(pack="srd-2014", collection="classes", index="wizard")
FIGHTER = ContentRef(pack="srd-2014", collection="classes", index="fighter")


def _content() -> Content:
    return load((PACK_DIR,), pack_format())


def test_weapon_dice_picks_the_versatile_expression_only_two_handed() -> None:
    content = _content()

    longsword = content.require(LONGSWORD, WeaponRecord)
    assert (longsword.damage, longsword.versatile_damage) == ("1d8", "1d10")
    assert longsword.dice(two_handed=False) == "1d8"
    assert longsword.dice(two_handed=True) == "1d10"


def test_weapon_of_reads_the_first_weapons_ref_on_an_items_sheet() -> None:
    content = _content()
    carried = Sheet(kind="item", refs=(LANTERN, LONGSWORD))

    facts = weapon_of(content, carried)

    assert facts is not None
    assert facts.damage == "1d8"
    assert weapon_of(content, Sheet(kind="item", refs=(LANTERN,))) is None


def test_spell_amounts_scale_by_slot_or_for_a_cantrip_by_caster_level() -> None:
    """`damage_at`/`heal_at` pick the base row below the first threshold and the scaled row at
    and above it."""
    content = _content()

    magic_missile = content.require(MAGIC_MISSILE, SpellRecord)
    assert magic_missile.damage_at(1) == SpellAmount(dice="3d4 + 3")
    assert magic_missile.damage_at(2) == SpellAmount(dice="4d4 + 4")

    burning_hands = content.require(BURNING_HANDS, SpellRecord)
    assert burning_hands.damage_at(1) == SpellAmount(dice="3d6")
    assert burning_hands.damage_at(2) == SpellAmount(dice="4d6")

    fire_bolt = content.require(FIRE_BOLT, SpellRecord)
    assert fire_bolt.level is None
    assert fire_bolt.damage_at(4) == SpellAmount(dice="1d10")
    assert fire_bolt.damage_at(5) == SpellAmount(dice="2d10")

    cure_wounds = content.require(CURE_WOUNDS, SpellRecord)
    heal = cure_wounds.heal
    assert heal is not None and heal.with_modifier is True
    assert (heal.dice, heal.bonus(2)) == ("1d8", 2)
    heal_at_two = cure_wounds.heal_at(2)
    assert heal_at_two is not None and heal_at_two.dice == "2d8"


def test_spell_of_raises_for_a_ref_that_names_no_spell() -> None:
    content = _content()

    with pytest.raises(ValueError, match="names no spell"):
        _ = spell_of(content, str(LONGSWORD))


def test_spellcasting_ability_reads_the_class_record_and_none_for_a_class_that_casts_none() -> None:
    content = _content()

    assert spellcasting_ability(content, Sheet(kind="actor", refs=(WIZARD,))) == "intelligence"
    assert spellcasting_ability(content, Sheet(kind="actor", refs=(FIGHTER,))) is None
