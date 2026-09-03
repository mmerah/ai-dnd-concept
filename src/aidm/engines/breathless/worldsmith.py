from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.breathless.world import SKILLS

AUTHORING = (
    "BREATHLESS AUTHORING\n"
    "The cast carries no dice: an NPC is a name, a brief and whether the player has met them, "
    "nothing more. A threat is a brief the player's own roll meets, never a stat block. "
    "Use the pack's `locations`, `complications` and `missions` as the setting's vocabulary."
)


class Pack(ScenePack):
    """One published table set the player can build a survivor from."""

    source: str
    license: str
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
            raise Refusal("the six SRD skills, by id")
        return self
