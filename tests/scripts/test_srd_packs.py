from pathlib import Path

import pytest
from srd_packs import convert, dump

from aidm.core.entities import Refusal
from aidm.core.io import read_model
from aidm.engines.loner3e.worldsmith import Loner3ePack

FIXTURE = Path(__file__).parents[1] / "fixtures" / "srd" / "AP01_fantasy.md"
PACKS_DIR = Path(__file__).parents[2] / "src/aidm/engines/loner3e/packs"
SHIPPED = PACKS_DIR / "ap01-fantasy.json"
SRD_IDS = set(read_model(PACKS_DIR / "srd.json", Loner3ePack).defined_ids())
SHIPPED_PACKS = sorted(PACKS_DIR.glob("ap*.json"))
TEXT = FIXTURE.read_text(encoding="utf-8")
STEM = "AP01_fantasy"
LOCATIONS_HEADING = "## Locations"
SEEDS_HEADING = "## Adventure Seeds"
SPELL_HEADER = "| D66 | Spell |"
ELDRIDA_HEADING = "### Eldrida (The Thorn-Crowned Capital)"
PARAGRAPH_LOCATION = (
    "### Eldrida (The Thorn-Crowned Capital)\n"
    "\n"
    "A capital behind fortified walls.\n"
    "**Encounters**:\n"
    "- King Vaelor\n"
    "- Keeper Ysryn\n"
    "\n"
    "### Catacombs of Eldrida"
)
DROPPED_CONCEPTS_ROW = (
    "| 6   | Sea-worn corsair      | Regal matriarch        | Masked fool with secrets "
    "| Master tactician   | Hard-bitten navigator  | Renowned artisan         |\n"
)
CROWN_OF_THORNS_CONCEPT = "- **Concept:** Embattled Monarch  \n"


def test_the_four_trait_tables_and_name_lists_are_each_thirty_six() -> None:
    pack = convert(TEXT, STEM)
    assert len(pack.concepts) == 36
    assert len(pack.skills) == 36
    assert len(pack.frailties) == 36
    assert len(pack.gear) == 36
    assert len(pack.names.female) == 36
    assert len(pack.names.male) == 36
    assert len(pack.names.surnames) == 36
    assert len(pack.names.nicknames) == 36


def test_the_cast_locations_and_seeds_are_counted() -> None:
    pack = convert(TEXT, STEM)
    assert len(pack.factions) == 6
    assert len(pack.npcs) == 6
    assert len(pack.monsters) == 6
    assert len(pack.locations) == 6
    assert len(pack.seeds) == 36


def test_a_frailty_labelled_with_a_diacritic_folds_to_a_plain_id() -> None:
    pack = convert(TEXT, STEM)
    naive = next(option for option in pack.frailties if option.label == "Naïve")
    assert naive.id == "naive"


def test_the_special_rule_becomes_prose_that_spends_luck() -> None:
    pack = convert(TEXT, STEM)
    assert pack.rules.startswith(
        "A character may channel their **Luck** to cast spells or activate magical abilities."
    )
    assert "- **Heal** (1 Luck)" in pack.rules
    assert "Spells:" in pack.rules.splitlines()
    assert pack.spends_luck


def test_the_first_location_carries_its_encounters_apart_from_its_detail() -> None:
    pack = convert(TEXT, STEM)
    first = pack.locations[0]
    assert first.label == "Eldrida (The Thorn-Crowned Capital)"
    assert first.encounters.startswith("**King Vaelor**")


def test_the_first_npc_carries_its_frailties_and_gear() -> None:
    pack = convert(TEXT, STEM)
    first = pack.npcs[0]
    assert first.frailties == ("Bound by blood-pact to an ancient oath",)
    assert len(first.gear) == 2


def test_converting_twice_gives_byte_identical_json() -> None:
    assert dump(convert(TEXT, STEM)) == dump(convert(TEXT, STEM))


def test_the_shipped_pack_matches_the_fixture_byte_for_byte() -> None:
    assert SHIPPED.read_text(encoding="utf-8") == dump(convert(TEXT, STEM))


def test_a_trait_table_missing_a_row_is_refused_naming_the_heading() -> None:
    assert TEXT.count(DROPPED_CONCEPTS_ROW) == 1
    broken = TEXT.replace(DROPPED_CONCEPTS_ROW, "", 1)
    with pytest.raises(Refusal, match="Concepts"):
        convert(broken, STEM)


def test_an_unknown_field_key_is_refused_naming_the_block_and_the_key() -> None:
    assert TEXT.count(CROWN_OF_THORNS_CONCEPT) == 1
    broken = TEXT.replace(CROWN_OF_THORNS_CONCEPT, "- **Weakness:** x  \n", 1)
    with pytest.raises(Refusal, match="The Crown of Thorns"):
        convert(broken, STEM)
    with pytest.raises(Refusal, match="Weakness"):
        convert(broken, STEM)


def test_a_level_one_locations_heading_still_yields_six_locations() -> None:
    assert TEXT.count(LOCATIONS_HEADING) == 1
    grown = TEXT.replace(LOCATIONS_HEADING, f"#{LOCATIONS_HEADING[1:]}", 1)
    assert len(convert(grown, STEM).locations) == 6


def test_an_empty_duplicate_seeds_heading_is_skipped_for_the_one_with_rows() -> None:
    assert TEXT.count(SEEDS_HEADING) == 1
    grown = TEXT.replace(SEEDS_HEADING, f"{SEEDS_HEADING}\n{SEEDS_HEADING}", 1)
    assert len(convert(grown, STEM).seeds) == 36


def test_a_location_written_as_a_paragraph_splits_at_its_encounters_line() -> None:
    assert TEXT.count(ELDRIDA_HEADING) == 1
    grown = TEXT.replace(ELDRIDA_HEADING, PARAGRAPH_LOCATION, 1)
    first = convert(grown, STEM).locations[0]
    assert first.detail == "A capital behind fortified walls."
    assert first.encounters == "King Vaelor; Keeper Ysryn"


def test_a_rules_table_with_a_roll_column_keeps_the_roll_value() -> None:
    assert TEXT.count(SPELL_HEADER) == 1
    grown = TEXT.replace(SPELL_HEADER, "| Roll | Spell |", 1)
    assert "- 11: **Heal** (1 Luck)" in convert(grown, STEM).rules


def test_twelve_adventure_packs_ship() -> None:
    assert len(SHIPPED_PACKS) == 12


@pytest.mark.parametrize("path", SHIPPED_PACKS, ids=lambda path: path.stem)
def test_every_shipped_pack_is_a_full_kit_that_shares_no_id_with_the_srd(path: Path) -> None:
    pack = read_model(path, Loner3ePack)

    assert len(pack.concepts) == 36
    assert len(pack.skills) == 36
    assert len(pack.frailties) == 36
    assert len(pack.gear) == 36
    assert len(pack.seeds) == 36
    assert len(pack.locations) == 6
    assert len(pack.factions) == 6
    assert len(pack.npcs) == 6
    assert len(pack.monsters) == 6
    assert not set(pack.defined_ids()) & SRD_IDS
