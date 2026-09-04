from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import EntityId, Mutable
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.base import Counter, Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

type Die = Literal[4, 6, 8, 10, 12]
LADDER: tuple[Die, ...] = (4, 6, 8, 10, 12)
type Skill = Literal["bash", "dash", "sneak", "shoot", "think", "sway"]
SKILLS: tuple[Skill, ...] = ("bash", "dash", "sneak", "shoot", "think", "sway")
SKILL_SPREAD = [4, 4, 4, 6, 8, 10]
STRESS_MAX = 4  # vulnerable at 4
CARRY = 3  # items beside the med kit
LOOT_START: Die = 12
STUNT_DIE: Die = 12
STARTING_ITEM: Die = 10
MED_KIT_CLEARS = 2


class Item(Mutable):
    name: str
    die: Die


class Survivor(Person):
    """The played character: the only one with dice."""

    pronouns: str = ""
    job: str = ""
    skills: dict[Skill, Die] = Field(min_length=6, max_length=6)  # as created
    worn: dict[Skill, Die] = Field(min_length=6, max_length=6)  # where each stands now
    items: dict[EntityId, Item] = Field(default_factory=dict)  # the backpack
    med_kit: bool = False
    loot: Die = LOOT_START
    stress: Counter = Field(default_factory=lambda: Counter(current=0, maximum=STRESS_MAX))
    stunted: bool = False

    @model_validator(mode="after")
    def _rated_spread(self) -> Self:
        if sorted(self.skills.values()) != SKILL_SPREAD:
            raise ValueError("skills as created: three d4, one d6, one d8, one d10")
        return self

    @property
    def vulnerable(self) -> bool:
        return self.stress.current >= STRESS_MAX

    def rows(self) -> Rows:
        skills = ", ".join(
            f"{skill.capitalize()} d{self.worn[skill]}"
            + ("" if self.worn[skill] == self.skills[skill] else f" (rated d{self.skills[skill]})")
            for skill in SKILLS
        )
        return tuple(
            (label, value)
            for label, value in (
                ("Pronouns", self.pronouns),
                ("Job", self.job),
                ("Skills", skills),
                ("Loot die", f"d{self.loot}"),
                ("Stress", str(self.stress) + (", vulnerable" if self.vulnerable else "")),
                ("Stunt", "spent" if self.stunted else ""),
                ("Med kit", "yes" if self.med_kit else ""),
            )
            if value
        )


BreathlessWorld = SceneWorld[Person, Survivor]


class BreathlessGame(Game[BreathlessWorld]):
    pass


class BreathlessScenario(Scenario[SceneCanon[Person]]):
    pass


class BreathlessCharacter(Character[Survivor]):
    pass


def stepped(die: Die) -> Die:
    """One step down the ladder, floored at d4."""
    return LADDER[max(LADDER.index(die) - 1, 0)]
