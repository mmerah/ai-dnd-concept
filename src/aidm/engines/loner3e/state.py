from typing import Annotated, Literal

from pydantic import Field

from aidm.kits.scenes.state import SceneCanon, SceneState
from aidm.state.entities import Counter, Mutable, Slug, pool

# Loner 3e's numbers; docs/LONER-3E.md points at the SRD and its deviations.
LUCK_MAX = 6
TIES_PER_TWIST = 3
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
AND_AT = 4  # both dice 4+ sharpens the answer to -and
BUT_AT = 3  # both dice 3 or under softens it to -but

SRD_PACK: Slug = "srd"


def _full_luck() -> Counter:
    return Counter(current=LUCK_MAX, maximum=LUCK_MAX)


class ActorSheet(Mutable):
    """What the player, an NPC or anything with a will rolls by."""

    kind: Literal["actor"] = "actor"
    chapters: int = Field(default=0, ge=0)
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    luck: Counter = Field(default_factory=_full_luck)
    milestones: int = Field(default=0, ge=0)

    def rows(self) -> tuple[tuple[str, str], ...]:
        return (
            ("Concept", self.concept),
            ("Skills", ", ".join(self.skills)),
            ("Frailties", ", ".join(self.frailties)),
            ("Gear", ", ".join(self.gear)),
            ("Luck", pool(self.luck)),
        )


class ItemSheet(Mutable):
    """SRD "Everything is a Character": a door, a storm or a curse resists with luck of its own."""

    kind: Literal["item"] = "item"
    luck: Counter = Field(default_factory=_full_luck)

    def rows(self) -> tuple[tuple[str, str], ...]:
        return (("Luck", pool(self.luck)),)


# A plain assignment, not `type`: a `type` alias defeats the discriminator.
LonerSheet = Annotated[ActorSheet | ItemSheet, Field(discriminator="kind")]

type LonerWorld = SceneState[LonerSheet]


class Loner3eState(Mutable):
    """The save payload: the scene world, plus the two counters the SRD keeps beside it."""

    engine: Literal["loner3e"] = "loner3e"
    world: SceneState[LonerSheet]
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Field(default_factory=lambda: Counter(current=0, maximum=TIES_PER_TWIST))
    # None rolls twists from the game's own first table set, so no scenario has to name one.
    twist_pack: Slug | None = None


class Loner3eScenario(Mutable):
    engine: Literal["loner3e"] = "loner3e"
    world: SceneCanon[LonerSheet]


class Loner3eCharacter(Mutable):
    engine: Literal["loner3e"] = "loner3e"
    sheet: ActorSheet
    twist_pack: Slug
