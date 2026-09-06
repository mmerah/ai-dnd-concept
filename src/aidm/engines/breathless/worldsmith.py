from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen
from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.breathless.world import SKILLS, Die, Skill, check_spread

AUTHORING = (
    "BREATHLESS AUTHORING\n"
    "The cast carries no dice until the player hires them in play. An npc is a name, a brief, "
    "and whether the player has met them. A threat is a brief that the player's own roll meets, "
    "never a stat block. Use the pack's `locations`, `complications` and `missions` as the "
    "setting's vocabulary."
)
HIRING = (
    "The player has hired {name}, {brief}, on these terms: {terms}. Write their sheet as "
    "someone who could plausibly be hired for this work. Give them pronouns and a job from "
    "this pack's list: {jobs}. Rate the six skills, with the best where the job and the terms "
    "point. Give them one item, and this pack's weapons are: {weapons}."
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
    """A hired survivor's sheet."""

    pronouns: str = Field(min_length=1, description="Their pronouns.")
    job: str = Field(min_length=1, description="Their job, one of the pack's or one like them.")
    skills: dict[Skill, Die] = Field(
        min_length=6,
        max_length=6,
        description="All six skills: three at d4, one d6, one d8 and one d10.",
    )
    item: str = Field(
        min_length=1,
        description="The one d10 item they carry: a weapon or a tool, named plainly.",
    )

    @model_validator(mode="after")
    def _rated_spread(self) -> Self:
        check_spread(self.skills)
        return self
