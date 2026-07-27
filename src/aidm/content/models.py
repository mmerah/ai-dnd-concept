"""A pack: a manifest and the records it provides.

The record models themselves live in `records/`, one module per family. This module owns only what
addresses and groups them, so adding a collection touches a field, a `collection()` arm and a
`Library` accessor — never the loader, the writer or the manifest check."""

from collections.abc import Mapping
from typing import Self, assert_never, get_args

from pydantic import Field, NonNegativeInt, model_validator

from ..utils.models import Frozen, FrozenMap
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


# A pack that ships none of a collection. Pydantic builds each field its own default from this, so
# the collections below do not share one mapping.
_EMPTY = Field(default_factory=dict, validate_default=True)


class Pack(Frozen):
    """One loaded pack: a manifest and the records it provides, keyed by index."""

    manifest: Manifest
    monsters: FrozenMap[str, MonsterRecord] = _EMPTY
    weapons: FrozenMap[str, WeaponRecord] = _EMPTY
    armor: FrozenMap[str, ArmorRecord] = _EMPTY
    gear: FrozenMap[str, GearRecord] = _EMPTY
    tools: FrozenMap[str, ToolRecord] = _EMPTY
    vehicles: FrozenMap[str, VehicleRecord] = _EMPTY
    magic_items: FrozenMap[str, MagicItemRecord] = _EMPTY
    spells: FrozenMap[str, SpellRecord] = _EMPTY
    skills: FrozenMap[str, SkillRecord] = _EMPTY
    conditions: FrozenMap[str, ConditionRecord] = _EMPTY
    alignments: FrozenMap[str, AlignmentRecord] = _EMPTY
    languages: FrozenMap[str, LanguageRecord] = _EMPTY
    classes: FrozenMap[str, ClassRecord] = _EMPTY
    subclasses: FrozenMap[str, SubclassRecord] = _EMPTY
    levels: FrozenMap[str, LevelRecord] = _EMPTY
    features: FrozenMap[str, FeatureRecord] = _EMPTY
    races: FrozenMap[str, RaceRecord] = _EMPTY
    subraces: FrozenMap[str, SubraceRecord] = _EMPTY
    traits: FrozenMap[str, TraitRecord] = _EMPTY
    backgrounds: FrozenMap[str, BackgroundRecord] = _EMPTY
    feats: FrozenMap[str, FeatRecord] = _EMPTY
    proficiencies: FrozenMap[str, ProficiencyRecord] = _EMPTY

    def collection(self, name: Collection) -> Mapping[str, Record]:
        match name:
            case "monsters":
                return self.monsters
            case "weapons":
                return self.weapons
            case "armor":
                return self.armor
            case "gear":
                return self.gear
            case "tools":
                return self.tools
            case "vehicles":
                return self.vehicles
            case "magic_items":
                return self.magic_items
            case "spells":
                return self.spells
            case "skills":
                return self.skills
            case "conditions":
                return self.conditions
            case "alignments":
                return self.alignments
            case "languages":
                return self.languages
            case "classes":
                return self.classes
            case "subclasses":
                return self.subclasses
            case "levels":
                return self.levels
            case "features":
                return self.features
            case "races":
                return self.races
            case "subraces":
                return self.subraces
            case "traits":
                return self.traits
            case "backgrounds":
                return self.backgrounds
            case "feats":
                return self.feats
            case "proficiencies":
                return self.proficiencies
            case _:
                assert_never(name)

    @model_validator(mode="after")
    def _matches_its_manifest(self) -> Self:
        """Fails here rather than mid-turn: a mis-keyed collection, or a file truncated since the
        manifest was written."""
        for name in COLLECTIONS:
            records = self.collection(name)
            wrong = sorted(k for k, r in records.items() if k != r.index)
            if wrong:
                raise ValueError(f"{name} keyed against the wrong index: {wrong}")
            declared = self.manifest.provides[name]
            if declared != len(records):
                raise ValueError(
                    f"manifest promises {declared} {name}, the pack ships {len(records)}"
                )
        return self
