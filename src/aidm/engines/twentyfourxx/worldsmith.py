from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen
from aidm.core.play import DecisionOption
from aidm.engines.base import Pack as ScenePack
from aidm.engines.twentyfourxx.world import Kit, SkillDie

AUTHORING = (
    "24XX AUTHORING\n"
    "The cast carries no dice until the player hires them in play: an NPC is a name, a brief "
    "and whether the player has met them, nothing more. A threat is a brief the player's own "
    "roll meets, never a stat block. The player is an operator on a job in a hard sci-fi future; "
    "write scenes as work sites, stations, ships and the people holding them."
)
HIRING = (
    "The player has hired {name} ({brief}) on these terms: {terms}. Write their sheet from the "
    "specialties and skills in ENGINE GUIDANCE, as someone who could plausibly be hired for this."
)


class SkillChoice(DecisionOption):
    """One printed pick: Muscle's Hand-to-hand or Shooting; Psychic's both at d8 or one at d10."""

    skills: dict[str, SkillDie]


class Specialty(DecisionOption):
    skills: dict[str, SkillDie]  # the fixed ones, at d8
    choice: tuple[SkillChoice, ...] = ()  # Muscle, Psychic
    kit: tuple[Kit, ...] = ()
    kit_choice: tuple[Kit, ...] = ()  # Muscle: "a sword, firearm, or cyber-arm" -- pick one


class Body(DecisionOption):
    kit: Kit | None = None  # the android case is an item that breaks to defend


class Origin(DecisionOption):
    increases: int = 0  # human 3, android 1
    invents: int = 0  # alien 2
    choice: tuple[Body, ...] = ()  # android: synth skin | case


class Pack(ScenePack):
    skills: tuple[DecisionOption, ...] = Field(min_length=17, max_length=17)
    specialties: tuple[Specialty, ...]
    origins: tuple[Origin, ...]
    starting_kit: tuple[Kit, ...]  # the comm

    @model_validator(mode="after")
    def _every_pick_told(self) -> Self:
        """A pick's detail is its prompt text, so a pack may not leave it blank."""
        untold = [option.id for option in (*self.specialties, *self.origins) if not option.detail]
        if untold:
            raise ValueError(f"no detail for {', '.join(untold)}")
        return self


class SheetDraft(Frozen):
    """A hired member's sheet, checked against the pack by `sheet_refusal`."""

    specialty: str = Field(description="One of the specialties in ENGINE GUIDANCE.")
    skills: dict[str, SkillDie] = Field(
        min_length=1,
        max_length=3,
        description="One to three skills, each named as ENGINE GUIDANCE lists them, at d8, d10 "
        "or d12; the specialty's own skills belong here.",
    )
    items: tuple[str, ...] = Field(
        max_length=3, description="What they carry, three at most, named plainly."
    )
    hindrances: tuple[str, ...] = Field(
        default=(),
        description="What already slows them down, if anything: an injury, a debt, a fear.",
    )


def hire_guidance(pack: Pack) -> str:
    lines = [_specialty_line(specialty) for specialty in pack.specialties]
    labels = ", ".join(option.label for option in pack.skills)
    return "\n".join((*lines, f"Skills: {labels}"))


def sheet_refusal(draft: SheetDraft, pack: Pack) -> str | None:
    """`None` when the pack can back every claim the draft makes; else what is wrong, joined."""
    problems: list[str] = []
    if draft.specialty not in {specialty.label for specialty in pack.specialties}:
        problems.append(f"{draft.specialty!r} is not a specialty this pack lists")
    listed = {option.label for option in pack.skills}
    granted = {
        skill
        for specialty in pack.specialties
        for skill in (
            *specialty.skills,
            *(name for option in specialty.choice for name in option.skills),
        )
    }
    if unknown := sorted(set(draft.skills) - listed - granted):
        problems.append(f"{', '.join(unknown)} is not a skill this pack lists or grants")
    if len(set(draft.items)) != len(draft.items):
        problems.append("an item repeats")
    return "; ".join(problems) or None


def _specialty_line(specialty: Specialty) -> str:
    fixed = ", ".join(f"{skill} d{die}" for skill, die in specialty.skills.items())
    if not specialty.choice:
        return f"{specialty.label}: {fixed}"
    alternatives = " / ".join(
        ", ".join(f"{skill} d{die}" for skill, die in option.skills.items())
        for option in specialty.choice
    )
    if fixed:
        return f"{specialty.label}: {fixed} plus one of: {alternatives}"
    return f"{specialty.label}: one of: {alternatives}"
