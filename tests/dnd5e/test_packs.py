from pathlib import Path

from fivee_test_support import PACK_DIR, dnd5e_game, pack_format

from aidm.state.base import EntityId
from aidm.state.packs import ENCODING, ContentRef, Record, read_pack, write_pack
from aidm.state.world import player_sheet

GIANT_RAT = ContentRef(pack="srd-2014", collection="monsters", index="giant-rat")
RAT = EntityId("cloister_rat")


def test_a_loaded_pack_writes_back_byte_for_byte(tmp_path: Path) -> None:
    """The format regression: a pack read and written again is the file that shipped."""
    write_pack(tmp_path, read_pack(PACK_DIR, pack_format()))

    for shipped in sorted(PACK_DIR.glob("*.json")):
        assert (tmp_path / shipped.name).read_text(encoding=ENCODING) == shipped.read_text(
            encoding=ENCODING
        )


def test_the_manifest_censuses_the_pack_and_pins_its_source() -> None:
    pack = read_pack(PACK_DIR, pack_format())

    assert pack.manifest.provides == {name: len(records) for name, records in pack.records.items()}
    assert pack.manifest.source_commit is not None


def test_the_shipped_character_carries_the_canonical_keys() -> None:
    """`armor-class` is authored content now, not the 10 the typed engine hard-coded."""
    _, state = dnd5e_game()

    player = player_sheet(state)

    assert (player.numbers["armor-class"], player.numbers["level"]) == (12, 1)
    assert player.counters["hp"].maximum == 11
    assert player.counters["second-wind"].recharge == "short-rest"


def test_a_monster_ref_becomes_the_monsters_sheet() -> None:
    """The loader's one mapping: a record's numbers land as numbers, except where the template
    declares a counter, which the record fills; its notes render beside the ref instead."""
    engine, state = dnd5e_game()
    record = read_pack(PACK_DIR, pack_format()).addressed()[GIANT_RAT]
    assert type(record) is Record

    world_record = state.world.record(RAT)
    sheet = world_record.rules

    assert sheet.counters["hp"].current == record.sheet_numbers()["hp"]
    assert sheet.counters["hp"].maximum == record.sheet_numbers()["hp"]
    assert sheet.numbers["armor-class"] == record.sheet_numbers()["armor-class"]
    assert sheet.refs == (GIANT_RAT,)
    assert "attacks=Bite +4 to hit" in engine.entity_state(world_record.entity, sheet)


def test_the_pack_renders_spell_and_weapon_mechanics_from_stored_maps() -> None:
    """The regression for the model's view: regenerating the pack must keep the structured facts
    the director acts on without a `read_content` round-trip, now stored at authoring time."""
    records = read_pack(PACK_DIR, pack_format()).addressed()
    burning_hands = records[ContentRef(pack="srd-2014", collection="spells", index="burning-hands")]
    fire_bolt = records[ContentRef(pack="srd-2014", collection="spells", index="fire-bolt")]
    hold_person = records[ContentRef(pack="srd-2014", collection="spells", index="hold-person")]
    longsword = records[ContentRef(pack="srd-2014", collection="weapons", index="longsword")]
    assert type(burning_hands) is Record
    assert type(fire_bolt) is Record
    assert type(hold_person) is Record
    assert type(longsword) is Record

    assert burning_hands.noted()["level"] == "1"
    assert burning_hands.noted()["save"] == "DEX (half on success)"
    assert burning_hands.noted()["damage"] == "3d6 fire"
    assert burning_hands.noted()["scaling"].startswith("slot 2: 4d6")
    assert fire_bolt.noted()["level"] == "cantrip"
    assert fire_bolt.noted()["attack"] == "ranged spell attack"
    assert fire_bolt.noted()["scaling"] == "level 5: 2d10, level 11: 3d10, level 17: 4d10"
    assert fire_bolt.noted()["classes"] == "Sorcerer, Wizard"
    assert hold_person.tags == ("concentration", "verbal", "somatic", "material")
    assert "versatile" in longsword.tags
    assert "slashing" in longsword.tags
    assert longsword.sheet_numbers()["damage-dice-count"] == 1
    assert longsword.sheet_numbers()["damage-die"] == 8
    assert longsword.sheet_numbers()["two-handed-damage-die"] == 10
    # A melee weapon's upstream `range.normal: 5` is baseline reach, not a ranged distance.
    assert "range-normal" not in longsword.sheet_numbers()
    assert longsword.sheet_numbers()["cost-gp"] == 15


def test_the_pack_projects_armor_and_monster_facts_into_numbers_and_tags() -> None:
    """Upstream ints become numbers, upstream booleans become tags, on single-backing records.
    Armor ships generic: its numbers are stored at authoring time, not computed."""
    records = read_pack(PACK_DIR, pack_format()).addressed()
    chain_mail = records[ContentRef(pack="srd-2014", collection="armor", index="chain-mail")]
    leather = records[ContentRef(pack="srd-2014", collection="armor", index="leather-armor")]
    dragon = records[ContentRef(pack="srd-2014", collection="monsters", index="adult-black-dragon")]
    assert type(chain_mail) is Record
    assert type(leather) is Record
    assert type(dragon) is Record

    assert chain_mail.sheet_numbers()["armor-base"] == 16
    assert chain_mail.sheet_numbers()["strength-minimum"] == 13
    assert chain_mail.tags == ("stealth-disadvantage",)
    assert leather.sheet_numbers() == {"cost-gp": 10, "armor-base": 11}
    assert leather.tags == ("add-dex-modifier",)
    assert dragon.sheet_numbers()["saving-throw-dex"] == 7
    assert dragon.sheet_numbers()["passive-perception"] == 21


def test_the_pack_projects_monster_action_variants_and_spell_lists() -> None:
    """Choice-shaped damage, choice-shaped multiattacks, save-gated riders and spell lists all
    come from structured upstream fields, not from `desc` prose."""
    records = read_pack(PACK_DIR, pack_format()).addressed()
    wight = records[ContentRef(pack="srd-2014", collection="monsters", index="wight")]
    captain = records[ContentRef(pack="srd-2014", collection="monsters", index="bandit-captain")]
    assassin = records[ContentRef(pack="srd-2014", collection="monsters", index="assassin")]
    acolyte = records[ContentRef(pack="srd-2014", collection="monsters", index="acolyte")]
    assert type(wight) is Record
    assert type(captain) is Record
    assert type(assassin) is Record
    assert type(acolyte) is Record

    assert "1d8+2 slashing (one handed) or 1d10+2 slashing (two handed)" in wight.noted()["attacks"]
    assert captain.noted()["multiattack"] == "2x Scimitar + 1x Dagger or 2x Dagger"
    assert "7d6 poison (DC 15 CON, half on save)" in assassin.noted()["attacks"]
    assert acolyte.noted()["spells"].startswith("cantrips: Light, Sacred Flame, Thaumaturgy")
    assert acolyte.noted()["slots"] == "level 1 x3"


def test_the_pack_projects_creation_choices_and_class_ladders() -> None:
    """A trait that grants a pick names it in `options`/`choose`; the odd class ladders land as
    notes on the level row."""
    records = read_pack(PACK_DIR, pack_format()).addressed()
    cantrip = records[ContentRef(pack="srd-2014", collection="traits", index="high-elf-cantrip")]
    tools = records[ContentRef(pack="srd-2014", collection="traits", index="tool-proficiency")]
    acolyte = records[ContentRef(pack="srd-2014", collection="backgrounds", index="acolyte")]
    sorcerer = records[ContentRef(pack="srd-2014", collection="levels", index="sorcerer-3")]
    barbarian = records[ContentRef(pack="srd-2014", collection="levels", index="barbarian-20")]
    assert type(cantrip) is Record
    assert type(tools) is Record
    assert type(acolyte) is Record
    assert type(sorcerer) is Record
    assert type(barbarian) is Record

    assert cantrip.choose == 1
    assert {option.collection for option in cantrip.options} == {"spells"}
    assert tools.choose == 1
    assert {option.collection for option in tools.options} == {"proficiencies"}
    assert acolyte.sheet_numbers() == {"starting-gold": 15}
    assert sorcerer.noted()["creating-spell-slots"].startswith("slot 1 for 2 sorcery points")
    assert barbarian.noted()["rage-count"] == "unlimited"
    assert "rage-count" not in barbarian.sheet_numbers()
