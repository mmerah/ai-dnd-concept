from typing import Annotated, Self

from pydantic import Field, model_validator

from ...content.records.base import Collection, ContentRef
from ...content.records.spells import SlotLevel
from ...content.vocabulary import RestType
from ...utils.models import SLUG_MAX_LENGTH, Ability, Attributes, Frozen, FrozenMap, Slug

MAX_LEVEL = 20

type Decisions = FrozenMap[Slug, tuple[Slug, ...]]


# A ContentRef flattened to a string, because a map key must survive a JSON round trip.
type FeatureKey = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9-]+/features/[a-z0-9-]+$",
        max_length=2 * SLUG_MAX_LENGTH + len("/features/"),
    ),
]
type SpellKey = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9-]+/spells/[a-z0-9-]+$",
        max_length=2 * SLUG_MAX_LENGTH + len("/spells/"),
    ),
]


def _key(ref: ContentRef, collection: Collection) -> str:
    if ref.collection != collection:
        raise ValueError(f"{ref} is not a {collection} record")
    return str(ref)


def feature_key(ref: ContentRef) -> FeatureKey:
    return _key(ref, "features")


def spell_key(ref: ContentRef) -> SpellKey:
    return _key(ref, "spells")


def spell_ref(key: SpellKey) -> ContentRef:
    """The inverse of `spell_key`; the key's pattern guarantees the three parts."""
    pack, _, index = key.split("/")
    return ContentRef(pack=pack, collection="spells", index=index)


class ResourceState(Frozen):
    """A pool of uses that a rest refills: a feature's counter, or one level of spell slots."""

    remaining: int = Field(ge=0)
    maximum: int = Field(ge=1)
    recharge: RestType

    @model_validator(mode="after")
    def _within_maximum(self) -> Self:
        if self.remaining > self.maximum:
            raise ValueError(f"resource has {self.remaining} uses, maximum {self.maximum}")
        return self

    @property
    def spent(self) -> int:
        return self.maximum - self.remaining

    def refills(self, completed: RestType) -> bool:
        return self.spent > 0 and (self.recharge == "short" or completed == "long")


type FeatureResources = FrozenMap[FeatureKey, ResourceState]
type SpellSlots = FrozenMap[SlotLevel, ResourceState]


class Origin(Frozen):
    class_ref: ContentRef
    race_ref: ContentRef | None = None
    subrace_ref: ContentRef | None = None
    background_ref: ContentRef | None = None
    subclass_ref: ContentRef | None = None


class Progression(Frozen):
    origin: Origin
    level: int = Field(ge=1, le=MAX_LEVEL)
    level_up_available: bool = False
    prof_bonus: int = Field(ge=2)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...]
    spell_slots: SpellSlots
    chosen_spells: tuple[ContentRef, ...]
    decisions: Decisions
    features: tuple[ContentRef, ...]
    feature_resources: FeatureResources

    @model_validator(mode="after")
    def _no_repeated_proficiency(self) -> Self:
        if len(set(self.proficiencies)) != len(self.proficiencies):
            raise ValueError(f"proficiency held twice: {sorted(self.proficiencies)}")
        if len(set(self.features)) != len(self.features):
            raise ValueError(f"feature held twice: {sorted(str(ref) for ref in self.features)}")
        chosen = [spell_key(ref) for ref in self.chosen_spells]
        if len(set(chosen)) != len(chosen):
            raise ValueError(f"spell chosen twice: {sorted(chosen)}")
        keys = {feature_key(ref) for ref in self.features}
        if unknown := sorted(set(self.feature_resources) - keys):
            raise ValueError(f"feature resources recorded for unheld features: {unknown}")
        if self.level_up_available and self.level >= MAX_LEVEL:
            raise ValueError(f"level {MAX_LEVEL} cannot have another level-up available")
        return self


class Advancement(Frozen):
    progression: Progression
    attributes: Attributes
    hp_gain: int = Field(ge=1)
