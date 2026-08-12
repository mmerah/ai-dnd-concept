from collections.abc import Mapping
from pathlib import Path

from fivee_test_support import PACK_DIR
from golden_test_support import golden_json
from pydantic import JsonValue

from aidm.engines.dnd5e.content import pack_format
from aidm.state.packs import read_pack

FIXTURE = Path(__file__).parent / "fixtures" / "mechanics_parity.json"


def test_the_shipped_pack_yields_the_same_spell_and_weapon_mechanics() -> None:
    """The mechanics the resolver runs every shipped record on are stored facts now: moving any
    of this either way is a behaviour change. The extraction spells out the fixture's original
    keys, so field restructuring cannot slip a value change past it."""
    pack = read_pack(PACK_DIR, pack_format())
    extracted = {
        "spells": {
            index: _spell(record.name, record.facts)
            for index, record in pack.records["spells"].items()
        },
        "weapons": {
            index: _weapon(record.name, record.facts)
            for index, record in pack.records["weapons"].items()
        },
    }
    golden_json(FIXTURE, extracted)


def _spell(name: str, facts: Mapping[str, JsonValue]) -> object:
    return {
        "name": name,
        "level": facts.get("level"),
        "attack-type": facts.get("attack-type"),
        "save-ability": facts.get("save-ability"),
        "save-success": facts.get("save-success"),
        "damage-type": facts.get("damage-type"),
        "concentration": facts.get("concentration", False),
        "damage-with-modifier": facts.get("damage-with-modifier", False),
        "heal-with-modifier": facts.get("heal-with-modifier", False),
        "damage-ladder": facts.get("damage-ladder"),
        "heal-ladder": facts.get("heal-ladder"),
    }


def _weapon(name: str, facts: Mapping[str, JsonValue]) -> object:
    return {
        "name": name,
        "damage": facts.get("damage"),
        "versatile-damage": facts.get("versatile-damage"),
        "damage-type": facts.get("damage-type"),
        "finesse": facts.get("finesse", False),
        "ranged": facts.get("ranged", False),
    }
