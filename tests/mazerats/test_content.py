from pathlib import Path
from random import Random

from aidm.engines.core import load_packs
from aidm.engines.mazerats.creation import Pack, spell_name

PACK_DIR = Path(__file__).parents[2] / "src/aidm/engines/mazerats/packs"
PACK = load_packs((PACK_DIR,), Pack)["srd"]


def test_srd_pack_ships_the_official_tables_and_its_attribution() -> None:
    assert "CC BY 4.0" in PACK.license
    assert "Ben Milton" in PACK.attribution
    assert "rules.moddable.games" in PACK.source
    required = {
        "physical-effects",
        "ethereal-forms",
        "monster-features",
        "civilized-npcs",
        "dungeon-rooms",
        "starting-items",
        "light-weapons",
    }
    assert required <= PACK.tables.keys()
    assert PACK.tables["starting-items"].entries[0] == "Animal scent"
    assert "Halberds" in PACK.tables["heavy-weapons"].entries


def test_table_lengths_are_the_source_lengths_and_odd_ones_are_noted() -> None:
    for key, table in PACK.tables.items():
        assert table.note or len(table.entries) == 36, key


def test_spell_name_joins_the_two_tables_its_formula_names() -> None:
    name = spell_name(PACK, Random(3))
    formula = PACK.formulas[Random(3).randint(1, 12) - 1]
    firsts = PACK.tables[formula.first].entries
    seconds = PACK.tables[formula.second].entries
    assert any(name == f"{first} {second}" for first in firsts for second in seconds)
