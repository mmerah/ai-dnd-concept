from typing import Literal

from pydantic import Field

from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import Counter, Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

LUCK_MAX = 6
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
TIES_PER_TWIST = 3

TagKind = Literal["skill", "frailty", "gear", "condition"]


class Loner3eSheet(Person):
    """SRD "Everything is a Character": a person, an object, a vehicle or a curse alike."""

    concept: str = ""
    tags: dict[TagKind, list[str]] = Field(default_factory=dict)
    # Living characters only; the SRD gives none to an object, a vehicle or a curse.
    goal: str = ""
    motive: str = ""
    nemesis: str = ""
    luck: Counter = Field(default_factory=lambda: Counter(current=LUCK_MAX, maximum=LUCK_MAX))

    def tagged(self, kind: TagKind) -> list[str]:
        return self.tags.get(kind, [])

    def rows(self) -> Rows:
        return tuple(
            (label, value)
            for label, value in (
                ("Concept", self.concept),
                ("Skills", ", ".join(self.tagged("skill"))),
                ("Frailties", ", ".join(self.tagged("frailty"))),
                ("Gear", ", ".join(self.tagged("gear"))),
                ("Conditions", ", ".join(self.tagged("condition"))),
                ("Goal", self.goal),
                ("Motive", self.motive),
                ("Nemesis", self.nemesis),
                ("Luck", str(self.luck)),
            )
            if value
        )

    def unwritten(self) -> str:
        missing = [
            why
            for why, held in (("alive", self.alive), ("full luck", self.luck.current == LUCK_MAX))
            if not held
        ]
        return ", ".join(missing)


class Loner3eWorld(SceneWorld[Loner3eSheet, Loner3eSheet]):
    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Field(default_factory=lambda: Counter(current=0, maximum=TIES_PER_TWIST))


class Loner3eGame(Game[Loner3eWorld]):
    pass


class Loner3eScenario(Scenario[SceneCanon[Loner3eSheet]]):
    pass


class Loner3eCharacter(Character[Loner3eSheet]):
    pass
