from fivee_test_support import PACK_DIR, pack_format

from aidm.state.packs import Content, ContentRef, Record, load

LONGSWORD = ContentRef(pack="srd-2014", collection="weapons", index="longsword")
DAGGER = ContentRef(pack="srd-2014", collection="weapons", index="dagger")
SHORTBOW = ContentRef(pack="srd-2014", collection="weapons", index="shortbow")
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


def test_weapon_facts_carry_damage_and_the_versatile_expression() -> None:
    content = _content()

    longsword = content.require(LONGSWORD, Record)
    assert longsword.facts == {
        "cost-gp": 15,
        "damage": "1d8",
        "versatile-damage": "1d10",
        "damage-type": "slashing",
    }
    assert "damage" not in content.require(LANTERN, Record).facts


def test_weapon_facts_flag_finesse_and_ranged() -> None:
    content = _content()

    assert content.require(DAGGER, Record).facts.get("finesse") is True
    assert content.require(SHORTBOW, Record).facts.get("ranged") is True


def test_magic_missile_is_a_leveled_spell_with_no_attack_or_save() -> None:
    content = _content()

    magic_missile = content.require(MAGIC_MISSILE, Record)
    assert magic_missile.facts.get("level") == 1
    assert "attack-type" not in magic_missile.facts
    assert "save-ability" not in magic_missile.facts
    ladder = magic_missile.facts.get("damage-ladder")
    assert isinstance(ladder, list)
    assert ladder[0] == [0, "3d4 + 3"]


def test_burning_hands_is_a_save_for_half_spell() -> None:
    content = _content()

    burning_hands = content.require(BURNING_HANDS, Record)
    assert burning_hands.facts.get("save-ability") == "dexterity"
    assert burning_hands.facts.get("save-success") == "half"
    ladder = burning_hands.facts.get("damage-ladder")
    assert isinstance(ladder, list)
    assert ladder[0] == [0, "3d6"]


def test_fire_bolt_is_a_cantrip_ranged_spell_attack() -> None:
    content = _content()

    fire_bolt = content.require(FIRE_BOLT, Record)
    assert "level" not in fire_bolt.facts
    assert fire_bolt.facts.get("attack-type") == "ranged"
    assert fire_bolt.facts.get("damage-ladder") == [
        [0, "1d10"],
        [5, "2d10"],
        [11, "3d10"],
        [17, "4d10"],
    ]


def test_cure_wounds_heals_with_a_modifier_and_carries_no_damage_ladder() -> None:
    content = _content()

    cure_wounds = content.require(CURE_WOUNDS, Record)
    ladder = cure_wounds.facts.get("heal-ladder")
    assert isinstance(ladder, list)
    assert ladder[0] == [0, "1d8"]
    assert cure_wounds.facts.get("heal-with-modifier") is True
    assert "damage-ladder" not in cure_wounds.facts


def test_hold_person_is_a_concentration_save_or_suffer_spell() -> None:
    content = _content()

    hold_person = content.require(HOLD_PERSON, Record)
    assert hold_person.facts.get("concentration") is True
    assert hold_person.facts.get("save-success") == "none"


def test_spellcasting_ability_is_a_class_fact_absent_for_a_class_that_casts_none() -> None:
    content = _content()

    assert content.require(WIZARD, Record).facts.get("spellcasting") == "intelligence"
    assert "spellcasting" not in content.require(FIGHTER, Record).facts
