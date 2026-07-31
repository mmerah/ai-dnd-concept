from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import get_args

from pydantic import TypeAdapter

from aidm.base import Kind

from .records.base import Collection, Record
from .records.character import (
    BackgroundRecord,
    ClassLevelRecord,
    ClassRecord,
    EquipmentProficiency,
    FeatRecord,
    FeatureRecord,
    LevelRecord,
    ProficiencyRecord,
    RaceRecord,
    SaveProficiency,
    SkillProficiency,
    SubclassLevelRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
)
from .records.equipment import (
    ArmorRecord,
    GearRecord,
    MagicItemRecord,
    ToolRecord,
    VehicleRecord,
    WeaponRecord,
)
from .records.monsters import MonsterRecord
from .records.rules import AlignmentRecord, ConditionRecord, LanguageRecord, SkillRecord
from .records.spells import SpellRecord


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    """Keeps classes explicit to avoid depending on Pydantic internals."""

    adapter: TypeAdapter[Record]
    classes: tuple[type[Record], ...]
    entity: Kind | None = None


def _holding(record: type[Record], entity: Kind | None = None) -> CollectionSpec:
    return CollectionSpec(TypeAdapter[Record](record), (record,), entity)


COLLECTION_SPECS: Mapping[Collection, CollectionSpec] = {
    "monsters": _holding(MonsterRecord, "actor"),
    "weapons": _holding(WeaponRecord, "item"),
    "armor": _holding(ArmorRecord, "item"),
    "gear": _holding(GearRecord, "item"),
    "tools": _holding(ToolRecord, "item"),
    "vehicles": _holding(VehicleRecord, "item"),
    "magic_items": _holding(MagicItemRecord, "item"),
    "spells": _holding(SpellRecord),
    "skills": _holding(SkillRecord),
    "conditions": _holding(ConditionRecord),
    "alignments": _holding(AlignmentRecord),
    "languages": _holding(LanguageRecord),
    "classes": _holding(ClassRecord),
    "subclasses": _holding(SubclassRecord),
    "levels": CollectionSpec(
        TypeAdapter[Record](LevelRecord),
        (ClassLevelRecord, SubclassLevelRecord),
    ),
    "features": _holding(FeatureRecord),
    "races": _holding(RaceRecord),
    "subraces": _holding(SubraceRecord),
    "traits": _holding(TraitRecord),
    "backgrounds": _holding(BackgroundRecord),
    "feats": _holding(FeatRecord),
    "proficiencies": CollectionSpec(
        TypeAdapter[Record](ProficiencyRecord),
        (EquipmentProficiency, SkillProficiency, SaveProficiency),
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
