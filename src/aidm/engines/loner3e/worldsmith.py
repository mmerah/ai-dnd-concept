from typing import Self

from pydantic import Field, model_validator

from aidm.core.entities import Frozen, Slug
from aidm.core.play import DecisionOption
from aidm.core.prompt import Sections
from aidm.engines.loner3e.world import DIE_FACE
from aidm.engines.packs import Pack, block_line, bullets

AUTHORING = (
    "LONER 3E AUTHORING\n"
    "Every character is a person, an object, a vehicle or a curse alike. Each one has a "
    "one-line `concept`, any fitting `tags` by kind, and luck of its own. The kinds are "
    "`skill`, `frailty` and `gear`. "
    "Luck says how long they hold out in a conflict, not how healthy they are: 6 for someone who "
    "can stand against the player, 2 or 3 for minor opposition that folds in an exchange or two. "
    "Write a group of like opponents as one character with one luck pool for their whole strength, "
    "not as several. Write `luck` full: `current` equal to `maximum`. "
    "A living character can carry a `goal`, a `motive` and a `nemesis`. An object, a vehicle "
    "and a curse do not. "
    "Every scene bears on the player's `goal`, or brings their `nemesis` nearer. "
    "Give a door or a storm the `skill` and `frailty` tags it resists with. "
    "Loner tags are freeform descriptions. Use selected pack entries when they fit. Invent "
    "scenario-specific tags when they are clearer. Only a pack tag carries a meaning the game "
    "master can look up. An invented tag that does not say what it does needs one sentence in "
    "that character's `brief`. Positions are judged from it. "
    "A pack's factions, people and monsters are written to be used: file one into `cast` under "
    "a new id, with its tags and drives copied and a `brief` for this scene, and size its luck "
    "by the rule above. Names come from the pack's name lists when the setting has them."
)


class Loner3eBlock(Frozen):
    """A faction, an NPC or a monster as the SRD prints it; the worldsmith copies it into cast."""

    name: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    skills: tuple[str, ...] = Field(min_length=1)
    frailties: tuple[str, ...] = Field(min_length=1)
    gear: tuple[str, ...] = ()
    goal: str = ""
    motive: str = ""
    nemesis: str = ""

    @property
    def line(self) -> str:
        return block_line(
            self.name,
            self.concept,
            ("skills", ", ".join(self.skills)),
            ("frailties", ", ".join(self.frailties)),
            ("gear", ", ".join(self.gear)),
            ("goal", self.goal),
            ("motive", self.motive),
            ("nemesis", self.nemesis),
        )


class Loner3ePack(Pack):
    concepts: tuple[DecisionOption, ...] = Field(min_length=1)
    skills: tuple[DecisionOption, ...] = Field(min_length=1)
    frailties: tuple[DecisionOption, ...] = Field(min_length=1)
    gear: tuple[DecisionOption, ...] = Field(min_length=1)
    spends_luck: bool = False  # AP01: `rules` spends Luck, so `spend_luck` is allowed
    factions: tuple[Loner3eBlock, ...] = ()
    npcs: tuple[Loner3eBlock, ...] = ()
    monsters: tuple[Loner3eBlock, ...] = ()
    twist_subjects: tuple[str, ...] | None = None
    twist_actions: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def _twist_columns_pair_up(self) -> Self:
        if (self.twist_subjects is None) != (self.twist_actions is None):
            raise ValueError("twist_subjects and twist_actions come together or not at all")
        for column in (self.twist_subjects, self.twist_actions):
            if column is not None and len(column) != DIE_FACE:
                raise ValueError("a twist column is one d6: exactly six entries")
        return self

    def defined_ids(self) -> tuple[Slug, ...]:
        return tuple(
            option.id for option in (*self.concepts, *self.skills, *self.frailties, *self.gear)
        )

    @property
    def counts(self) -> tuple[tuple[str, int], ...]:
        return (
            ("concepts", len(self.concepts)),
            ("skills", len(self.skills)),
            ("frailties", len(self.frailties)),
            ("gear", len(self.gear)),
            ("factions", len(self.factions)),
            ("people", len(self.npcs)),
            ("monsters", len(self.monsters)),
            *super().counts,
        )

    def sections(self, *, opening: bool) -> Sections:
        tags = "\n".join(
            f"{kind}: {', '.join(option.label for option in options)}"
            for kind, options in (
                ("concepts", self.concepts),
                ("skills", self.skills),
                ("frailties", self.frailties),
                ("gear", self.gear),
            )
        )
        return (
            *super().sections(opening=opening),
            ("TRAIT TAGS", tags),
            *bullets("FACTIONS", (block.line for block in self.factions)),
            *bullets("PEOPLE", (block.line for block in self.npcs)),
            *bullets("MONSTERS", (block.line for block in self.monsters)),
        )
