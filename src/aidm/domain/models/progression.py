from typing import Annotated, Self

from pydantic import Field, model_validator

from ...content.records.base import ContentRef
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


class FeatureResourceState(Frozen):
    remaining: int = Field(ge=0)
    maximum: int = Field(ge=1)
    recharge: RestType

    @model_validator(mode="after")
    def _within_maximum(self) -> Self:
        if self.remaining > self.maximum:
            raise ValueError(f"feature resource has {self.remaining} uses, maximum {self.maximum}")
        return self


type FeatureResources = FrozenMap[FeatureKey, FeatureResourceState]


def feature_key(ref: ContentRef) -> FeatureKey:
    if ref.collection != "features":
        raise ValueError(f"{ref} is not a feature")
    return str(ref)


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
    spell_slots: FrozenMap[int, int]
    decisions: Decisions
    features: tuple[ContentRef, ...]
    feature_resources: FeatureResources

    @model_validator(mode="after")
    def _no_repeated_proficiency(self) -> Self:
        if len(set(self.proficiencies)) != len(self.proficiencies):
            raise ValueError(f"proficiency held twice: {sorted(self.proficiencies)}")
        if len(set(self.features)) != len(self.features):
            raise ValueError(f"feature held twice: {sorted(str(ref) for ref in self.features)}")
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
