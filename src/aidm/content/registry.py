from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import get_args

from pydantic import TypeAdapter

from ..utils.models import Kind
from . import records
from .records import Collection, Record


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    """Keeps classes explicit to avoid depending on Pydantic internals."""

    adapter: TypeAdapter[Record]
    classes: tuple[type[Record], ...]
    entity: Kind | None = None


def _holding(record: type[Record], entity: Kind | None = None) -> CollectionSpec:
    return CollectionSpec(TypeAdapter[Record](record), (record,), entity)


COLLECTION_SPECS: Mapping[Collection, CollectionSpec] = {
    "monsters": _holding(records.MonsterRecord, "actor"),
    "weapons": _holding(records.WeaponRecord, "item"),
    "armor": _holding(records.ArmorRecord, "item"),
    "gear": _holding(records.GearRecord, "item"),
    "tools": _holding(records.ToolRecord, "item"),
    "vehicles": _holding(records.VehicleRecord, "item"),
    "magic_items": _holding(records.MagicItemRecord, "item"),
    "spells": _holding(records.SpellRecord),
    "skills": _holding(records.SkillRecord),
    "conditions": _holding(records.ConditionRecord),
    "alignments": _holding(records.AlignmentRecord),
    "languages": _holding(records.LanguageRecord),
    "classes": _holding(records.ClassRecord),
    "subclasses": _holding(records.SubclassRecord),
    "levels": CollectionSpec(
        TypeAdapter[Record](records.LevelRecord),
        (records.ClassLevelRecord, records.SubclassLevelRecord),
    ),
    "features": _holding(records.FeatureRecord),
    "races": _holding(records.RaceRecord),
    "subraces": _holding(records.SubraceRecord),
    "traits": _holding(records.TraitRecord),
    "backgrounds": _holding(records.BackgroundRecord),
    "feats": _holding(records.FeatRecord),
    "proficiencies": CollectionSpec(
        TypeAdapter[Record](records.ProficiencyRecord),
        (records.EquipmentProficiency, records.SkillProficiency, records.SaveProficiency),
    ),
}

COLLECTION_OF: Mapping[type[Record], Collection] = {
    cls: name for name, spec in COLLECTION_SPECS.items() for cls in spec.classes
}


def _concrete(record: type[Record]) -> Iterator[type[Record]]:
    subclasses = record.__subclasses__()
    for subclass in subclasses:
        yield from _concrete(subclass)
    if not subclasses:
        yield record


# Prove the static key type and runtime routing table stay synchronized.
if _unspecified := sorted(set(get_args(Collection)) - set(COLLECTION_SPECS)):
    raise TypeError(f"collections with no spec: {_unspecified}")
if _unrouted := sorted(r.__name__ for r in _concrete(Record) if r not in COLLECTION_OF):
    raise TypeError(f"record classes in no collection: {_unrouted}")
