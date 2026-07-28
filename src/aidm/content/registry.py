"""One row per collection: how to validate it, which record classes it holds, and which kind of
entity may name it. Adding a collection is this row plus the record class — the loader, the writer,
the manifest check and every lookup read the answer from here rather than restating it."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import get_args

from pydantic import TypeAdapter

from ..utils.models import Kind
from . import records
from .records import Collection, Record


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    """`classes` cannot be derived from `adapter`: a discriminated union's core schema names no
    single class, and reading it would reach into pydantic internals."""

    adapter: TypeAdapter[Record]
    classes: tuple[type[Record], ...]
    entity: Kind | None = None  # the one kind of entity that may name a record here


def _holding(record: type[Record], entity: Kind | None = None) -> CollectionSpec:
    return CollectionSpec(TypeAdapter[Record](record), (record,), entity)


# Most collections name no entity kind: a spell is cast, never stood next to.
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

# The collection a record class belongs to, which is what a typed lookup checks a ref against.
COLLECTION_OF: Mapping[type[Record], Collection] = {
    cls: name for name, spec in COLLECTION_SPECS.items() for cls in spec.classes
}


def _concrete(record: type[Record]) -> Iterator[type[Record]]:
    """A class nothing extends; everything above one is shared shape no collection holds."""
    subclasses = record.__subclasses__()
    for subclass in subclasses:
        yield from _concrete(subclass)
    if not subclasses:
        yield record


# `Collection` stays the static key vocabulary — deriving it from this table would cost every keyed
# lookup its type check — so the table is what gets proved against it. Neither guard covers the
# other: a literal with no row loads nothing, a leaf class in no row is addressable by nothing.
if _unspecified := sorted(set(get_args(Collection)) - set(COLLECTION_SPECS)):
    raise TypeError(f"collections with no spec: {_unspecified}")
if _unrouted := sorted(r.__name__ for r in _concrete(Record) if r not in COLLECTION_OF):
    raise TypeError(f"record classes in no collection: {_unrouted}")
