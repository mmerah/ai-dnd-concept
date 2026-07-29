from typing import Self

from pydantic import Field, model_validator

from ...content.records.base import ContentRef
from ...utils.models import Ability, Attributes, Frozen, FrozenMap, Slug

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
    level_up_available: bool = False
    prof_bonus: int = Field(ge=2)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...]
    spell_slots: FrozenMap[int, int]
    decisions: Decisions

    @model_validator(mode="after")
    def _no_repeated_proficiency(self) -> Self:
        if len(set(self.proficiencies)) != len(self.proficiencies):
            raise ValueError(f"proficiency held twice: {sorted(self.proficiencies)}")
        if self.level_up_available and self.level >= MAX_LEVEL:
            raise ValueError(f"level {MAX_LEVEL} cannot have another level-up available")
        return self


class Advancement(Frozen):
    progression: Progression
    attributes: Attributes
    hp_gain: int = Field(ge=1)
