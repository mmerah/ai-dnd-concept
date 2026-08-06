from pathlib import Path

from fivee_test_support import PACK_DIR, pack_format
from golden_test_support import golden_json

from aidm.engines.dnd5e.records import SpellRecord, WeaponRecord
from aidm.state.packs import Record, read_pack

FIXTURE = Path(__file__).parent / "fixtures" / "mechanics_parity.json"
_WEAPON_FIELDS = {"damage", "versatile_damage", "ranged", "finesse"}


def test_the_shipped_pack_yields_the_same_spell_and_weapon_mechanics() -> None:
    """The mechanics the resolver runs every shipped record on: a null weapon is one it refuses,
    and moving any of this either way is a behaviour change. The extraction spells the fixture's
    original keys, so field restructuring cannot slip a value change past it."""
    pack = read_pack(PACK_DIR, pack_format())
    extracted = {
        "spells": {
            index: _spell(_typed(record, SpellRecord))
            for index, record in pack.records["spells"].items()
        },
        "weapons": {
            index: _weapon(_typed(record, WeaponRecord))
            for index, record in pack.records["weapons"].items()
        },
    }
    golden_json(FIXTURE, extracted)


def _spell(record: SpellRecord) -> object:
    return {
        "name": record.name,
        "level": record.level,
        "attack": record.attack,
        "save_ability": record.save_ability,
        "half_on_save": record.half_on_save,
        "damage": None if record.damage is None else record.damage.model_dump(mode="json"),
        "heal": None if record.heal is None else record.heal.model_dump(mode="json"),
        "scaling": [[at, amount.model_dump(mode="json")] for at, amount in record.scaling],
        "concentration": record.concentration,
    }


def _typed[R: Record](record: Record, held: type[R]) -> R:
    if not isinstance(record, held):
        raise TypeError(f"{record.index!r} is a {type(record).__name__}, not a {held.__name__}")
    return record


def _weapon(record: WeaponRecord) -> object:
    if record.damage is None:
        return None
    return record.model_dump(mode="json", include=_WEAPON_FIELDS)
