"""What the player has become: class, level, and the choices that made them that.

The static/mutable line, one level down from `StatBlock`. `Origin` and `decisions` are not
recoverable from any pack — they *are* the character; `prof_bonus`, `proficiencies` and
`spell_slots` are snapshots taken when a level was gained, like every other number a rule reads.
Feature text and spell descriptions stay in the pack and are read live."""

from typing import Self

from pydantic import Field, model_validator

from ...content import ContentRef
from ...content.records import Slug
from ...utils.models import Ability, Attributes, Frozen, FrozenMap

MAX_LEVEL = 20

# What the player picked, keyed by `ProgressionChoice.id`: the on-disk sheet, the stored progression
# and the engine's parameter are one type, so a decision cannot change shape on its way to state.
type Decisions = FrozenMap[Slug, tuple[Slug, ...]]


class Origin(Frozen):
    """Who a character is, as pack references. Only `class_ref` is required: a pack ships one
    background and no guarantee of races, so the rest are gaps a character may legally have."""

    class_ref: ContentRef
    race_ref: ContentRef | None = None
    subrace_ref: ContentRef | None = None
    background_ref: ContentRef | None = None
    subclass_ref: ContentRef | None = None


class Progression(Frozen):
    """`decisions` is the whole record of what the player picked — every proficiency and ability
    bonus below was derived from it. Nothing here has a default: each field is a snapshot the
    engine took, so a value it forgot to supply must not read as a plausible one.

    Save proficiency lives in `saving_throws` alone. A class states it twice upstream — as abilities
    and as `saving-throw-*` proficiency records — and one fact in two fields is one that can
    disagree with itself."""

    origin: Origin
    level: int = Field(ge=1, le=MAX_LEVEL)
    prof_bonus: int = Field(ge=2)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...]
    spell_slots: FrozenMap[int, int]
    decisions: Decisions

    @model_validator(mode="after")
    def _no_repeated_proficiency(self) -> Self:
        """A proficiency granted twice would be a bonus counted twice the moment expertise lands."""
        if len(set(self.proficiencies)) != len(self.proficiencies):
            raise ValueError(f"proficiency held twice: {sorted(self.proficiencies)}")
        return self


class Advancement(Frozen):
    """What gaining a level makes of a character. Creating one at level 1 and levelling up produce
    the same value, so `engine/progression.py` has one shape and the reducer one arm — and the hit
    points are a *gain* because a rolled hit die is not recomputable from anything else."""

    progression: Progression
    attributes: Attributes
    hp_gain: int = Field(ge=1)
