from collections.abc import Sequence
from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Refusal, Slug, check_unique, slug
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections, section_if
from aidm.engines.hiring import HIRED, UNWRITTEN_CAST
from aidm.engines.packs import (
    Named,
    Pack,
    PackBody,
    PackHead,
    block_line,
    bullets,
    check_items,
    check_lines,
)
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
            return f"{self.name}: {fixed}"
        alternatives = " / ".join(
            ", ".join(f"{skill} d{die}" for skill, die in option.skills.items())
            for option in self.choice
        )
        if fixed:
            return f"{self.name}: {fixed} plus one of: {alternatives}"
        return f"{self.name}: one of: {alternatives}"


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

    @model_validator(mode="after")
    def _reads_in_a_block(self) -> Self:
        check_lines("a block field", (self.name, self.brief))
        check_items("a block list", (*self.skills, *self.items, *self.hindrances))
        return self

    def line(self) -> str:
        return block_line(
            self.name,
            self.brief,
            ("skills", ", ".join(self.skills)),
            ("items", ", ".join(self.items)),
            ("hindrances", ", ".join(self.hindrances)),
        )


class TwentyfourxxPack(Pack):
    skills: tuple[DecisionOption, ...] = ()  # the SRD's seventeen; a written pack adds none
    specialties: tuple[Specialty, ...] = ()
    origins: tuple[Origin, ...] = ()
    starting_kit: tuple[Kit, ...] = ()
    factions: tuple[TwentyfourxxBlock, ...] = ()
    npcs: tuple[TwentyfourxxBlock, ...] = ()
    monsters: tuple[TwentyfourxxBlock, ...] = ()

    @model_validator(mode="after")
    def _every_pick_told(self) -> Self:
        """A pick's brief is its prompt text, so a pack may not leave it blank."""
        untold = [option.id for option in (*self.specialties, *self.origins) if not option.brief]
        if untold:
            raise ValueError(f"no brief for {', '.join(untold)}")
        return self

    def specialty_lines(self) -> str:
        return "\n".join(specialty.line() for specialty in self.specialties)

    def counts(self) -> tuple[tuple[str, int], ...]:
        return (
            ("specialties", len(self.specialties)),
            ("origins", len(self.origins)),
            ("factions", len(self.factions)),
            ("people", len(self.npcs)),
            ("monsters", len(self.monsters)),
            *super().counts(),
        )

    def sections(self, *, opening: bool) -> Sections:
        return (
            *super().sections(opening=opening),
            *section_if("SPECIALTIES", self.specialty_lines()),
            *bullets("ORIGINS", (f"{origin.name} — {origin.brief}" for origin in self.origins)),
            *bullets("FACTIONS", (block.line() for block in self.factions)),
            *bullets("PEOPLE", (block.line() for block in self.npcs)),
            *bullets("MONSTERS", (block.line() for block in self.monsters)),
        )


class SheetProposal(Frozen):
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
        specialties = {specialty.name for pack in packs for specialty in pack.specialties}
        if self.specialty not in specialties:
            raise Refusal(f"{self.specialty!r} is not a specialty these packs list")


class SpecialtyProposal(Named):
    """A written pack offers no picks-within-a-pick, so a specialty names its skills outright."""

    # `default=...` is pydantic for required: a pick's prompt text, which `Named` lets be empty.
    brief: str = Field(
        default=...,
        min_length=1,
        max_length=200,
        description="The line a player reads when picking this specialty, such as "
        "'You cut steel and read the welds'.",
    )
    skills: tuple[str, ...] = Field(
        min_length=1,
        max_length=3,
        description="The skills this specialty starts at d8, named plainly, such as 'Salvage'.",
    )
    kit: tuple[str, ...] = Field(
        default=(),
        max_length=3,
        description="What this specialty starts with, such as 'cutting torch'; empty where it "
        "starts with nothing of its own.",
    )

    @model_validator(mode="after")
    def _skills_are_distinct_and_read_in_a_block(self) -> Self:
        """A skill written twice would collapse into one die without a word."""
        check_unique("skills", self.skills)
        check_items("a specialty list", (*self.skills, *self.kit))
        return self


class OriginProposal(Named):
    """Where an operator comes from: what it hands them at creation, beyond the prose."""

    brief: str = Field(
        default=...,
        min_length=1,
        max_length=200,
        description="The line a player reads when picking this origin, such as "
        "'Born on the belt, and it shows'.",
    )
    increases: int = Field(
        default=0,
        ge=0,
        le=3,
        description="How many starting skills this origin raises one step, such as 3 for a "
        "generalist origin.",
    )
    invents: int = Field(
        default=0,
        ge=0,
        le=3,
        description="How many traits of their own this origin lets a player invent, such as 2 "
        "for an alien origin.",
    )


class TwentyfourxxHead(PackHead):
    specialties: tuple[SpecialtyProposal, ...] = Field(
        min_length=1, max_length=6, description="The trades a player picks their operator from."
    )
    origins: tuple[OriginProposal, ...] = Field(
        min_length=1, max_length=6, description="Where an operator can come from in this setting."
    )

    def pack_fields(self) -> dict[str, object]:
        taken: list[Slug] = []
        specialties: list[Specialty] = []
        for draft in self.specialties:
            # Appended as each id is made: two rows sharing a name must not share an id.
            specialties.append(
                Specialty(
                    id=slug(draft.name, taken),
                    name=draft.name,
                    brief=draft.brief,
                    skills=dict.fromkeys(draft.skills, 8),
                    kit=tuple(Kit(name=name) for name in draft.kit),
                )
            )
            taken.append(specialties[-1].id)
        origins: list[Origin] = []
        for draft in self.origins:
            origins.append(
                Origin(
                    id=slug(draft.name, taken),
                    name=draft.name,
                    brief=draft.brief,
                    increases=draft.increases,
                    invents=draft.invents,
                )
            )
            taken.append(origins[-1].id)
        return {
            **super().pack_fields(),
            "specialties": tuple(specialties),
            "origins": tuple(origins),
        }


class TwentyfourxxBody(PackBody):
    factions: tuple[TwentyfourxxBlock, ...] = Field(
        min_length=1,
        max_length=6,
        description="The powers that hold this setting, such as a company, a union or a fleet.",
    )
    npcs: tuple[TwentyfourxxBlock, ...] = Field(
        min_length=1, max_length=6, description="People a player could meet and work with."
    )
    monsters: tuple[TwentyfourxxBlock, ...] = Field(
        min_length=1,
        max_length=6,
        description="What stands against the player: a boarding crew, a drone, a thing in the "
        "hold.",
    )
