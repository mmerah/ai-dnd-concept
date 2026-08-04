from collections.abc import Iterator, Mapping
from typing import get_args

from pydantic import TypeAdapter

from aidm.core.base import Kind
from aidm.core.packs import CollectionSpec, PackFormat, Record

from .records.base import Collection
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


def _holding(record: type[Record], entity: Kind | None = None) -> CollectionSpec:
    return CollectionSpec(TypeAdapter[Record](record), (record,), entity)


# Keyed by `str`, not `Collection`: a `ContentRef` names a collection the way any engine's does.
COLLECTION_SPECS: Mapping[str, CollectionSpec] = {
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

PACK_FORMAT = PackFormat(COLLECTION_SPECS)


def _concrete(record: type[Record]) -> Iterator[type[Record]]:
    subclasses = record.__subclasses__()
    for subclass in subclasses:
        yield from _concrete(subclass)
    if not subclasses:
        yield record


# Prove the static key type and runtime routing table stay synchronized. `Record` is core's, so the
# walk keeps to this engine's own records: another engine's are not this table's to route.
if _drift := sorted(set(get_args(Collection)) ^ set(COLLECTION_SPECS)):
    raise TypeError(f"collections the spec table and the literal disagree on: {_drift}")
if _unrouted := sorted(
    record.__name__
    for record in _concrete(Record)
    if record.__module__.startswith(f"{__package__}.records")
    and not any(record in spec.classes for spec in COLLECTION_SPECS.values())
):
    raise TypeError(f"record classes in no collection: {_unrouted}")
