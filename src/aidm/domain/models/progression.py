from typing import Self

from pydantic import Field, model_validator

from ...content import ContentRef
from ...content.records import Slug
from ...utils.models import Ability, Attributes, Frozen, FrozenMap

MAX_LEVEL = 20

type Decisions = FrozenMap[Slug, tuple[Slug, ...]]


class Origin(Frozen):
    class_ref: ContentRef
    race_ref: ContentRef | None = None
    subrace_ref: ContentRef | None = None
    background_ref: ContentRef | None = None
    subclass_ref: ContentRef | None = None


class Progression(Frozen):
    origin: Origin
    level: int = Field(ge=1, le=MAX_LEVEL)
    prof_bonus: int = Field(ge=2)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...]
    spell_slots: FrozenMap[int, int]
    decisions: Decisions

    @model_validator(mode="after")
    def _no_repeated_proficiency(self) -> Self:
        if len(set(self.proficiencies)) != len(self.proficiencies):
            raise ValueError(f"proficiency held twice: {sorted(self.proficiencies)}")
        return self


class Advancement(Frozen):
    progression: Progression
    attributes: Attributes
    hp_gain: int = Field(ge=1)
