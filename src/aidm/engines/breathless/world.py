from functools import partial
from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.entities import EntityId, Mutable, slug
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Counter, Person, pool
from aidm.engines.scenes import SceneScenario, SceneState, SceneWorld

type Die = Literal[4, 6, 8, 10, 12]
LADDER: tuple[Die, ...] = (4, 6, 8, 10, 12)
type Skill = Literal["bash", "dash", "sneak", "shoot", "think", "sway"]
SKILLS: tuple[Skill, ...] = ("bash", "dash", "sneak", "shoot", "think", "sway")
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
    skills: dict[Skill, Die] = Field(default_factory=dict)  # as created
    worn: dict[Skill, Die] = Field(default_factory=dict)  # where each stands now
    items: dict[EntityId, Item] = Field(default_factory=dict)  # the backpack
    med_kit: bool = False
    loot: Die = LOOT_START
    stress: Counter = Field(default_factory=partial(Counter, current=0, maximum=STRESS_MAX))
    stunted: bool = False

    @model_validator(mode="after")
    def _filled_out(self) -> Self:
        for skill in SKILLS:
            self.skills.setdefault(skill, 4)
        for skill in SKILLS:
            self.worn.setdefault(skill, self.skills[skill])
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
                ("Stress", pool(self.stress) + (", vulnerable" if self.vulnerable else "")),
                ("Stunt", "spent" if self.stunted else ""),
                ("Med kit", "yes" if self.med_kit else ""),
            )
            if value
        )


BreathlessWorld = SceneWorld[Person, Survivor]
BreathlessState = SceneState[Person, Survivor]


class BreathlessCharacter(Mutable):
    pronouns: str
    job: str
    skills: dict[Skill, Die]
    item: str  # the one starting d10 item

    @model_validator(mode="after")
    def _three_skills(self) -> Self:
        if len(self.skills) != 3 or sorted(self.skills.values()) != [6, 8, 10]:
            raise ValueError("three skills: one d10, one d8, one d6")
        return self


class BreathlessGame(Game[BreathlessState]):
    pass


class BreathlessScenarioFile(Scenario[SceneScenario[Person]]):
    pass


class BreathlessCharacterFile(Character[BreathlessCharacter]):
    pass


def stepped(die: Die) -> Die:
    """One step down the ladder, floored at d4."""
    return LADDER[max(LADDER.index(die) - 1, 0)]


def player_survivor(character: BreathlessCharacterFile) -> Survivor:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    return Survivor(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        pronouns=payload.pronouns,
        job=payload.job,
        skills=payload.skills,
        items={EntityId(slug(payload.item, ())): Item(name=payload.item, die=STARTING_ITEM)},
    )
