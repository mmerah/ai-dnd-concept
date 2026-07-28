"""A pack: a manifest and the records it provides.

The record models themselves live in `records/`, one module per family. This module owns only what
addresses and groups them, so adding a collection touches a field and the record's own
`COLLECTION` — never the loader, the writer, the manifest check or a lookup."""

from collections.abc import Mapping
from typing import Self, cast, get_args

from pydantic import NonNegativeInt, model_validator

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap
from .records import (
    AlignmentRecord,
    ArmorRecord,
    BackgroundRecord,
    ClassRecord,
    Collection,
    ConditionRecord,
    FeatRecord,
    FeatureRecord,
    GearRecord,
    LanguageRecord,
    LevelRecord,
    MagicItemRecord,
    MonsterRecord,
    ProficiencyRecord,
    RaceRecord,
    Record,
    SkillRecord,
    Slug,
    SpellRecord,
    SubclassRecord,
    SubraceRecord,
    ToolRecord,
    TraitRecord,
    VehicleRecord,
    WeaponRecord,
)

COLLECTIONS: tuple[Collection, ...] = get_args(Collection)


class PackStamp(Frozen):
    id: Slug
    version: str


class Manifest(Frozen):
    """`provides` is the per-collection count `Pack` verifies its shipped records against — a
    truncated collection is caught here, where `extra="ignore"` cannot see it."""

    id: Slug
    name: str
    version: str
    edition: str
    requires: tuple[Slug, ...] = ()
    provides: FrozenMap[Collection, NonNegativeInt]

    @model_validator(mode="after")
    def _declares_every_collection(self) -> Self:
        """Every collection is counted, so a 0 is a *stated gap* rather than an omission: the SRD
        ships one background, and a character creator must say so up front rather than let the
        player discover it three levels in. Silence could not carry that."""
        if undeclared := sorted(set(COLLECTIONS) - set(self.provides)):
            raise ValueError(f"manifest declares no count for {undeclared}")
        return self

    @property
    def stamp(self) -> PackStamp:
        return PackStamp(id=self.id, version=self.version)


class Pack(Frozen):
    """One loaded pack: a manifest and the records it provides, keyed by index."""

    manifest: Manifest
    monsters: FrozenMap[str, MonsterRecord] = EMPTY_FROZEN_MAP
    weapons: FrozenMap[str, WeaponRecord] = EMPTY_FROZEN_MAP
    armor: FrozenMap[str, ArmorRecord] = EMPTY_FROZEN_MAP
    gear: FrozenMap[str, GearRecord] = EMPTY_FROZEN_MAP
    tools: FrozenMap[str, ToolRecord] = EMPTY_FROZEN_MAP
    vehicles: FrozenMap[str, VehicleRecord] = EMPTY_FROZEN_MAP
    magic_items: FrozenMap[str, MagicItemRecord] = EMPTY_FROZEN_MAP
    spells: FrozenMap[str, SpellRecord] = EMPTY_FROZEN_MAP
    skills: FrozenMap[str, SkillRecord] = EMPTY_FROZEN_MAP
    conditions: FrozenMap[str, ConditionRecord] = EMPTY_FROZEN_MAP
    alignments: FrozenMap[str, AlignmentRecord] = EMPTY_FROZEN_MAP
    languages: FrozenMap[str, LanguageRecord] = EMPTY_FROZEN_MAP
    classes: FrozenMap[str, ClassRecord] = EMPTY_FROZEN_MAP
    subclasses: FrozenMap[str, SubclassRecord] = EMPTY_FROZEN_MAP
    levels: FrozenMap[str, LevelRecord] = EMPTY_FROZEN_MAP
    features: FrozenMap[str, FeatureRecord] = EMPTY_FROZEN_MAP
    races: FrozenMap[str, RaceRecord] = EMPTY_FROZEN_MAP
    subraces: FrozenMap[str, SubraceRecord] = EMPTY_FROZEN_MAP
    traits: FrozenMap[str, TraitRecord] = EMPTY_FROZEN_MAP
    backgrounds: FrozenMap[str, BackgroundRecord] = EMPTY_FROZEN_MAP
    feats: FrozenMap[str, FeatRecord] = EMPTY_FROZEN_MAP
    proficiencies: FrozenMap[str, ProficiencyRecord] = EMPTY_FROZEN_MAP

    def collection(self, name: Collection) -> Mapping[str, Record]:
        """A field is named for the collection it holds, which is what makes this a lookup rather
        than a hand-written table. The cast stays: `getattr` off a non-literal name is typed `Any`,
        and an `Any` this code never wrote is worse than one it names."""
        return cast(Mapping[str, Record], getattr(self, name))

    @model_validator(mode="after")
    def _matches_its_manifest(self) -> Self:
        """Fails here rather than mid-turn: a mis-keyed collection, or a file truncated since the
        manifest was written."""
        for name in COLLECTIONS:
            records = self.collection(name)
            if wrong := sorted(k for k, r in records.items() if k != r.index):
                raise ValueError(f"{name} keyed against the wrong index: {wrong}")
            declared = self.manifest.provides[name]
            if declared != len(records):
                raise ValueError(
                    f"manifest promises {declared} {name}, the pack ships {len(records)}"
                )
        return self
