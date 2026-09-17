from collections.abc import Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Refusal, Slug, check_unique
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, section_if
from aidm.engines.packs import Pack, block_line, bullets
from aidm.engines.tools import HIRED, UNWRITTEN_CAST
from aidm.engines.twentyfourxx.world import Kit, SkillDie

AUTHORING = (
    "24XX AUTHORING\n"
    f"{UNWRITTEN_CAST}The player is an operator on a job in a hard science-fiction future. "
    "Write scenes as work sites, stations, ships, and the people who hold them."
)
HIRING = (
    f"{HIRED}Write their sheet from the specialties in ENGINE GUIDANCE. Write someone who "
    "could plausibly be hired for this work. The specialty's own skills belong in `skills`; "
    "invent a fitting skill beyond that list when none printed suits them."
)
SKILL_COUNT = 17


class SkillChoice(DecisionOption):
    """One printed pick: Muscle's Hand-to-hand or Shooting; Psychic's both at d8 or one at d10."""

    skills: dict[str, SkillDie]


class Specialty(DecisionOption):
    skills: dict[str, SkillDie]  # the fixed ones, at d8
    choice: tuple[SkillChoice, ...] = ()
    kit: tuple[Kit, ...] = ()
    kit_choice: tuple[Kit, ...] = ()  # Muscle: "a sword, firearm, or cyber-arm" -- pick one

    def line(self) -> str:
        fixed = ", ".join(f"{skill} d{die}" for skill, die in self.skills.items())
        if not self.choice:
            return f"{self.label}: {fixed}"
        alternatives = " / ".join(
            ", ".join(f"{skill} d{die}" for skill, die in option.skills.items())
            for option in self.choice
        )
        if fixed:
            return f"{self.label}: {fixed} plus one of: {alternatives}"
        return f"{self.label}: one of: {alternatives}"


class Body(DecisionOption):
    kit: Kit | None = None  # the android case is an item that breaks to defend


class Origin(DecisionOption):
    increases: int = 0  # human 3, android 1
    invents: int = 0  # alien 2
    choice: tuple[Body, ...] = ()


class TwentyfourxxBlock(Frozen):
    name: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    skills: tuple[str, ...] = Field(min_length=1)
    items: tuple[str, ...] = ()
    hindrances: tuple[str, ...] = ()

    @property
    def line(self) -> str:
        return block_line(
            self.name,
            self.brief,
            ("skills", ", ".join(self.skills)),
            ("items", ", ".join(self.items)),
            ("hindrances", ", ".join(self.hindrances)),
        )


class TwentyfourxxPack(Pack):
    skills: tuple[DecisionOption, ...] = ()  # the SRD's seventeen; a supplement adds none
    specialties: tuple[Specialty, ...] = ()
    origins: tuple[Origin, ...] = ()
    starting_kit: tuple[Kit, ...] = ()
    factions: tuple[TwentyfourxxBlock, ...] = ()
    npcs: tuple[TwentyfourxxBlock, ...] = ()
    hostiles: tuple[TwentyfourxxBlock, ...] = ()

    @model_validator(mode="after")
    def _every_pick_told(self) -> Self:
        """A pick's detail is its prompt text, so a pack may not leave it blank."""
        untold = [option.id for option in (*self.specialties, *self.origins) if not option.detail]
        if untold:
            raise ValueError(f"no detail for {', '.join(untold)}")
        return self

    def specialty_lines(self) -> str:
        return "\n".join(specialty.line() for specialty in self.specialties)

    def defined_ids(self) -> tuple[Slug, ...]:
        return tuple(option.id for option in (*self.specialties, *self.origins))

    @property
    def counts(self) -> tuple[tuple[str, int], ...]:
        return (
            ("specialties", len(self.specialties)),
            ("origins", len(self.origins)),
            ("factions", len(self.factions)),
            ("people", len(self.npcs)),
            ("hostiles", len(self.hostiles)),
            *super().counts,
        )

    def sections(self, *, opening: bool) -> Sections:
        return (
            *super().sections(opening=opening),
            *section_if("SPECIALTIES", self.specialty_lines()),
            *bullets("ORIGINS", (f"{origin.label} — {origin.detail}" for origin in self.origins)),
            *bullets("FACTIONS", (block.line for block in self.factions)),
            *bullets("PEOPLE", (block.line for block in self.npcs)),
            *bullets("HOSTILES", (block.line for block in self.hostiles)),
        )


class SheetDraft(Frozen):
    """A hired member's sheet."""

    specialty: str = Field(description="One of the specialties in ENGINE GUIDANCE.")
    skills: dict[str, SkillDie] = Field(
        min_length=1,
        max_length=3,
        description="One to three skills, at d8, d10 or d12. Prefer ENGINE GUIDANCE; invent one "
        "that fits when none printed does.",
    )
    items: tuple[str, ...] = Field(
        max_length=3, description="What they carry, three at most, named plainly."
    )
    hindrances: tuple[str, ...] = Field(
        default=(),
        description="What already slows them down, if anything: an injury, a debt, a fear.",
    )

    def check(self, packs: Sequence[TwentyfourxxPack]) -> None:
        check_unique("items", self.items)
        check_unique("hindrances", self.hindrances)
        specialties = {specialty.label for pack in packs for specialty in pack.specialties}
        if self.specialty not in specialties:
            raise Refusal(f"{self.specialty!r} is not a specialty these packs list")
