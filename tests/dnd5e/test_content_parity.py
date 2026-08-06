from collections.abc import Mapping
from pathlib import Path

from fivee_test_support import PACK_DIR, pack_format
from golden_test_support import golden_json

from aidm.core.packs import CollectionName, LenientRecord, Pack, Record, read_pack
from aidm.engines.dnd5e.content import SpellFacts, WeaponFacts

FIXTURE = Path(__file__).parent / "fixtures" / "mechanics_parity.json"


def test_the_shipped_pack_yields_the_same_spell_and_weapon_mechanics() -> None:
    """What the resolver can extract from every shipped record, including the records it cannot
    type: a null here is a spell that falls back to `improvise`, and moving one either way is a
    behaviour change."""
    pack = read_pack(PACK_DIR, pack_format())
    extracted = {
        "spells": {
            index: _dumped(SpellFacts.from_record(record))
            for index, record in _records(pack, "spells").items()
        },
        "weapons": {
            index: _dumped(WeaponFacts.from_record(record))
            for index, record in _records(pack, "weapons").items()
        },
    }
    golden_json(FIXTURE, extracted)


def _records(pack: Pack, collection: CollectionName) -> Mapping[str, LenientRecord]:
    return {index: _lenient(record) for index, record in pack.records[collection].items()}


def _lenient(record: Record) -> LenientRecord:
    if not isinstance(record, LenientRecord):
        raise TypeError(f"{record.index!r} is a {type(record).__name__}, not a LenientRecord")
    return record


def _dumped(facts: SpellFacts | WeaponFacts | None) -> object:
    return None if facts is None else facts.model_dump(mode="json")
