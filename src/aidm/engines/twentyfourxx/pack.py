from typing import Self

from pydantic import Field, model_validator

from aidm.state.base import Frozen
from aidm.state.creation import ContentSlug, CreationOption

from .mechanics import SkillDie


class SkillGrant(Frozen):
    """One side of a specialty's either/or: its skills land on the sheet at `die`."""

    id: ContentSlug
    label: str
    detail: str = ""
    skills: tuple[str, ...] = Field(min_length=1)
    die: SkillDie = 8


class Specialty(Frozen):
    """One of the SRD's six specialties: `skills` land at d8, `choices` offer one grant,
    and `kit` lands as traits on the created character."""

    id: ContentSlug
    label: str
    detail: str = ""
    skills: tuple[str, ...] = ()
    choices: tuple[SkillGrant, ...] = ()
    kit: tuple[CreationOption, ...] = ()

    @model_validator(mode="after")
    def _grants_a_skill_some_way(self) -> Self:
        if not self.skills and not self.choices:
            raise ValueError("a specialty grants at least one skill, fixed or chosen")
        return self


class Origin(Frozen):
    id: ContentSlug
    label: str
    detail: str = ""
    increases: int = Field(default=0, ge=0, le=3)
    # The menu an origin's invented traits are chosen from; `invents` of them are picked.
    traits: tuple[CreationOption, ...] = ()
    invents: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _invented_traits_fit_the_menu(self) -> Self:
        if self.invents > len(self.traits):
            raise ValueError(f"{self.invents} traits cannot be chosen from {len(self.traits)}")
        return self


class Pack(Frozen):
    """One published table set the player can build a character from."""

    name: str
    source: str
    license: str
    # What every character takes regardless of specialty: the SRD's comm.
    starting_kit: tuple[CreationOption, ...] = ()
    specialties: tuple[Specialty, ...] = Field(min_length=1)
    origins: tuple[Origin, ...] = Field(min_length=1)
    # The skill menu an origin's increases are chosen from.
    skills: tuple[CreationOption, ...] = Field(min_length=1)
