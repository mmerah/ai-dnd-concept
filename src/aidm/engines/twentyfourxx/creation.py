from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Refusal
from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.twentyfourxx.world import Kit, SkillDie

AUTHORING = (
    "24XX AUTHORING\n"
    "The cast carries no dice: an NPC is a name, a brief and whether the player has met them, "
    "nothing more. A threat is a brief the player's own roll meets, never a stat block. The "
    "player is an operator on a job in a hard sci-fi future; write scenes as work sites, "
    "stations, ships and the people holding them."
)


class SkillChoice(DecisionOption):
    """One printed pick: Muscle's Hand-to-hand or Shooting; Psychic's both at d8 or one at d10."""

    skills: dict[str, SkillDie]


class Specialty(DecisionOption):
    skills: dict[str, SkillDie]  # the fixed ones, at d8
    choice: tuple[SkillChoice, ...] = ()  # Muscle, Psychic
    kit: tuple[Kit, ...] = ()
    kit_choice: tuple[Kit, ...] = ()  # Muscle: "a sword, firearm, or cyber-arm" -- pick one


class Origin(DecisionOption):
    increases: int = 0  # human 3, android 1
    invents: int = 0  # alien 2
    choice: tuple[DecisionOption, ...] = ()  # android: synth skin | case


class Pack(ScenePack):
    source: str
    license: str
    skills: tuple[DecisionOption, ...] = Field(min_length=17, max_length=17)
    specialties: tuple[Specialty, ...]
    origins: tuple[Origin, ...]
    starting_kit: tuple[Kit, ...]  # the comm

    @model_validator(mode="after")
    def _every_pick_told(self) -> Self:
        """A pick's detail is its prompt text, so a pack may not leave it blank."""
        untold = [option.id for option in (*self.specialties, *self.origins) if not option.detail]
        if untold:
            raise Refusal(f"no detail for {', '.join(untold)}")
        return self
