from pathlib import Path

from fivee_test_support import PACK_DIR, dnd5e_game, pack_format

from aidm.state.base import EntityId
from aidm.state.packs import ENCODING, ContentRef, Record, read_pack, write_pack
from aidm.state.sheet import is_ladder_fact
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
    """The loader's one mapping: a record's int facts land as numbers, except where the template
    declares a counter, which the record fills; its other facts render beside the ref instead."""
    engine, state = dnd5e_game()
    record = read_pack(PACK_DIR, pack_format()).addressed()[GIANT_RAT]
    assert type(record) is Record

    world_record = state.world.record(RAT)
    sheet = world_record.rules

    assert sheet.counters["hp"].current == record.facts["hp"]
    assert sheet.counters["hp"].maximum == record.facts["hp"]
    assert sheet.numbers["armor-class"] == record.facts["armor-class"]
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

    assert burning_hands.facts["level"] == 1
    assert burning_hands.facts["save-ability"] == "dexterity"
    assert burning_hands.facts["save-success"] == "half"
    assert burning_hands.facts["damage-type"] == "fire"
    damage_ladder = burning_hands.facts["damage-ladder"]
    assert is_ladder_fact(damage_ladder) and damage_ladder[0] == [0, "3d6"]
    assert burning_hands.facts["area"] == "15-foot cone"
    # A cantrip has no `level` fact at all: `actions.json` reads its absence as the cantrip test.
    assert "level" not in fire_bolt.facts
    assert fire_bolt.facts["attack-type"] == "ranged"
    assert fire_bolt.facts["damage-ladder"] == [
        [0, "1d10"],
        [5, "2d10"],
        [11, "3d10"],
        [17, "4d10"],
    ]
    assert fire_bolt.facts["classes"] == "Sorcerer, Wizard"
    assert hold_person.tags == ("concentration", "verbal", "somatic", "material")
    assert "versatile" in longsword.tags
    assert "slashing" in longsword.tags
    assert longsword.facts["damage"] == "1d8"
    assert longsword.facts["versatile-damage"] == "1d10"
    assert longsword.facts["damage-type"] == "slashing"
    # A melee weapon's upstream `range.normal: 5` is baseline reach, not a ranged distance.
    assert "range-normal" not in longsword.facts
    assert longsword.facts["cost-gp"] == 15


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

    assert chain_mail.facts["armor-base"] == 16
    assert chain_mail.facts["strength-minimum"] == 13
    assert chain_mail.tags == ("stealth-disadvantage",)
    assert leather.facts == {"cost-gp": 10, "armor-base": 11}
    assert leather.tags == ("add-dex-modifier",)
    assert dragon.facts["saving-throw-dex"] == 7
    assert dragon.facts["passive-perception"] == 21


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

    wight_attacks = wight.facts["attacks"]
    assert isinstance(wight_attacks, str)
    assert "1d8+2 slashing (one handed) or 1d10+2 slashing (two handed)" in wight_attacks
    assert captain.facts["multiattack"] == "2x Scimitar + 1x Dagger or 2x Dagger"
    assassin_attacks = assassin.facts["attacks"]
    assert isinstance(assassin_attacks, str)
    assert "7d6 poison (DC 15 CON, half on save)" in assassin_attacks
    acolyte_spells = acolyte.facts["spells"]
    assert isinstance(acolyte_spells, str)
    assert acolyte_spells.startswith("cantrips: Light, Sacred Flame, Thaumaturgy")
    assert acolyte.facts["slots"] == [[1, 3]]


def test_the_pack_projects_creation_choices_and_class_ladders() -> None:
    """A trait that grants a pick names it in `options`/`choose`; the odd class ladders land as
    facts on the level row."""
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
    # backgrounds stop projecting: `starting-gold` is a creation input, not a live sheet number.
    assert acolyte.facts["starting-gold"] == 15
    slot_creation = sorcerer.facts["creating-spell-slots"]
    assert is_ladder_fact(slot_creation) and slot_creation[0] == [1, 2]
    assert barbarian.facts["rage-count"] == "unlimited"
