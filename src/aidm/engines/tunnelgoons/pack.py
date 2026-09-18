from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen
from aidm.core.prompt import Sections, section_if
from aidm.engines.packs import Pack, PackBody, PackHead, bullets, check_lines
from aidm.engines.tools import HIRED
from aidm.engines.tunnelgoons.world import ABILITY_POINTS, AbilityScores

AUTHORING = (
    "TUNNEL GOONS AUTHORING\n"
    "Every npc needs `hp`. It is the npc's Health and its Difficulty Score at once. Grade it "
    "as 8 easy, 10 moderate, or 12 hard. A pack's people and monsters are written to be met: "
    "file one as an npc under a new id, a monster with the `hp` the pack prints."
)
HIRE_GUIDANCE = (
    "TUNNEL GOONS HIRING\n"
    f"Spread {ABILITY_POINTS} points across three abilities. Brute is smacking things and "
    "feats of strength. Skulker is sneaking, aiming and balancing. Erudite is reading, "
    "perception and speaking. Answer with the abilities alone."
)
HIRING = (
    f"{HIRED}Write their three abilities from ENGINE GUIDANCE, to fit who they are and what "
    "they were hired for."
)


class TunnelGoonsBlock(Frozen):
    name: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    hp: int = Field(ge=1)  # Health and Difficulty Score at once: 8 easy, 10 moderate, 12 hard

    @model_validator(mode="after")
    def _reads_in_a_block(self) -> Self:
        check_lines("a block field", (self.name, self.brief))
        return self

    def line(self) -> str:
        return f"{self.name} — {self.brief} (hp {self.hp})"


class TunnelGoonsPack(Pack):
    items: tuple[str, ...] = ()  # names the create page hints with
    factions: tuple[TunnelGoonsBlock, ...] = ()
    npcs: tuple[TunnelGoonsBlock, ...] = ()
    monsters: tuple[TunnelGoonsBlock, ...] = ()

    def counts(self) -> tuple[tuple[str, int], ...]:
        return (
            ("items", len(self.items)),
            ("factions", len(self.factions)),
            ("people", len(self.npcs)),
            ("monsters", len(self.monsters)),
            *super().counts(),
        )

    def sections(self, *, opening: bool) -> Sections:
        return (
            *super().sections(opening=opening),
            *section_if("ITEMS", ", ".join(self.items)),
            *bullets("FACTIONS", (block.line() for block in self.factions)),
            *bullets("PEOPLE", (block.line() for block in self.npcs)),
            *bullets("MONSTERS", (block.line() for block in self.monsters)),
        )


class AbilitiesProposal(Frozen):
    abilities: AbilityScores = Field(
        min_length=3,
        max_length=3,
        description=(
            f"Points in brute, skulker and erudite: exactly {ABILITY_POINTS} across the three."
        ),
    )

    @model_validator(mode="after")
    def _points_spent(self) -> Self:
        total = sum(self.abilities.values())
        if total != ABILITY_POINTS:
            raise ValueError(
                f"the three abilities must share exactly {ABILITY_POINTS} points, not {total}"
            )
        return self


class TunnelGoonsHead(PackHead):
    items: tuple[str, ...] = Field(
        min_length=6,
        max_length=36,
        description="Things a goon could start with, named plainly, such as 'Bear trap'.",
    )

    @model_validator(mode="after")
    def _every_item_reads_on_one_line(self) -> Self:
        check_lines("an item", self.items)
        return self


class TunnelGoonsBody(PackBody):
    factions: tuple[TunnelGoonsBlock, ...] = Field(
        min_length=1,
        max_length=6,
        description="The powers that hold this setting, such as a guild, a cult or a warband.",
    )
    npcs: tuple[TunnelGoonsBlock, ...] = Field(
        min_length=1, max_length=6, description="People a player could meet and deal with."
    )
    monsters: tuple[TunnelGoonsBlock, ...] = Field(
        min_length=1,
        max_length=6,
        description="What stands against the player and is not a person: a beast, a horror, a "
        "thing in the dark.",
    )
