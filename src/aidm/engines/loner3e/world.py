from functools import partial
from typing import Literal

from pydantic import Field

from aidm.core.entities import Mutable
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Counter, Person, pool
from aidm.engines.scenes import SceneScenario, SceneState, SceneWorld

LUCK_MAX = 6
DIE_FACE = 6  # every roll in the game is one d6, and every table is six rows
TIES_PER_TWIST = 3

TagKind = Literal["skill", "frailty", "gear", "condition"]


class LonerCharacter(Person):
    """SRD "Everything is a Character": a person, an object, a vehicle or a curse alike."""

    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    # Living characters only; the SRD gives none to an object, a vehicle or a curse.
    goal: str = ""
    motive: str = ""
    nemesis: str = ""
    luck: Counter = Field(default_factory=partial(Counter, current=LUCK_MAX, maximum=LUCK_MAX))

    def rows(self) -> Rows:
        return tuple(
            (label, value)
            for label, value in (
                ("Concept", self.concept),
                ("Skills", ", ".join(self.skills)),
                ("Frailties", ", ".join(self.frailties)),
                ("Gear", ", ".join(self.gear)),
                ("Conditions", ", ".join(self.conditions)),
                ("Goal", self.goal),
                ("Motive", self.motive),
                ("Nemesis", self.nemesis),
                ("Luck", pool(self.luck)),
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


LonerWorld = SceneWorld[LonerCharacter, LonerCharacter]


class Loner3eState(SceneState[LonerCharacter, LonerCharacter]):
    """The save payload: the scene world, plus the counter the SRD keeps beside it."""

    # The played character's tally paces the whole game, so no sheet carries one.
    twist: Counter = Field(default_factory=partial(Counter, current=0, maximum=TIES_PER_TWIST))


class Loner3eCharacter(Mutable):
    concept: str = ""
    skills: tuple[str, ...] = ()
    frailties: tuple[str, ...] = ()
    gear: tuple[str, ...] = ()
    goal: str = ""
    motive: str = ""


class Loner3eGame(Game[Loner3eState]):
    pass


class Loner3eScenarioFile(Scenario[SceneScenario[LonerCharacter]]):
    pass


class Loner3eCharacterFile(Character[Loner3eCharacter]):
    pass


def player_character(character: Loner3eCharacterFile) -> LonerCharacter:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    return LonerCharacter(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        concept=payload.concept,
        skills=payload.skills,
        frailties=payload.frailties,
        gear=payload.gear,
        goal=payload.goal,
        motive=payload.motive,
    )


def tags_of(one: LonerCharacter, kind: TagKind) -> tuple[str, ...]:
    match kind:
        case "skill":
            return one.skills
        case "frailty":
            return one.frailties
        case "gear":
            return one.gear
        case "condition":
            return one.conditions


def set_tags(one: LonerCharacter, kind: TagKind, tags: tuple[str, ...]) -> None:
    match kind:
        case "skill":
            one.skills = tags
        case "frailty":
            one.frailties = tags
        case "gear":
            one.gear = tags
        case "condition":
            one.conditions = tags
