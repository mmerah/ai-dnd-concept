from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen
from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.breathless.world import SKILLS, Die, Skill, check_spread

AUTHORING = (
    "BREATHLESS AUTHORING\n"
    "The cast carries no dice until the player hires them in play: an NPC is a name, a brief "
    "and whether the player has met them, nothing more. A threat is a brief the player's own "
    "roll meets, never a stat block. Use the pack's `locations`, `complications` and `missions` "
    "as the setting's vocabulary."
)
HIRING = (
    "The player has hired {name} ({brief}) on these terms: {terms}. Write their sheet as "
    "someone who could plausibly be hired for this: pronouns, a job (this pack's: {jobs}), the "
    "six skills as created, and the one item they carry (weapons here: {weapons})."
)


class Pack(ScenePack):
    skills: tuple[DecisionOption, ...] = Field(min_length=6, max_length=6)
    jobs: tuple[str, ...]
    weapons: tuple[str, ...]
    long_range_weapons: tuple[str, ...]
    locations: tuple[str, ...]
    complications: tuple[str, ...] = Field(min_length=12, max_length=12)  # one d12
    missions: tuple[str, ...]

    @model_validator(mode="after")
    def _six_srd_skills(self) -> Self:
        if {skill.id for skill in self.skills} != set(SKILLS):
            raise ValueError("the six SRD skills, by id")
        return self


class SheetDraft(Frozen):
    """A hired survivor's sheet: the literal spread is the whole bar; no pack check follows."""

    pronouns: str = Field(min_length=1, description="Their pronouns.")
    job: str = Field(min_length=1, description="Their job, one of the pack's or one like them.")
    skills: dict[Skill, Die] = Field(
        min_length=6,
        max_length=6,
        description="All six skills as created: three at d4, one d6, one d8, one d10, the best "
        "where the job and the terms say.",
    )
    item: str = Field(
        min_length=1,
        description="The one d10 item they carry: a weapon or a tool, named plainly.",
    )

    @model_validator(mode="after")
    def _rated_spread(self) -> Self:
        check_spread(self.skills)
        return self
