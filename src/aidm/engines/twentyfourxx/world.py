from typing import Literal

from pydantic import Field

from aidm.core.entities import EntityId, Frozen, Mutable, slug
from aidm.core.model import Character, Game, Scenario
from aidm.core.views import Rows
from aidm.engines.core import PLAYER_ID, Person
from aidm.engines.scenes.world import SceneCanon, SceneWorld

type SkillDie = Literal[8, 10, 12]
LADDER: tuple[SkillDie, ...] = (8, 10, 12)
DEFAULT_DIE = 6  # a skill not on the sheet
HINDERED_DIE = 4
HELP_DIE = 6
STARTING_CREDITS = 2
MAIMED = "Maimed"


class Kit(Frozen):
    """An item as a pack or a character file names it."""

    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)


class Item(Mutable):
    name: str
    bulky: bool = False
    breaks: int = Field(default=1, ge=1)  # a vest breaks once; battle armor "up to 3x"
    broken_times: int = Field(default=0, ge=0)

    @property
    def broken(self) -> bool:
        return self.broken_times >= self.breaks


class Operator(Person):
    """The played character: the only one with dice, credits and hindrances."""

    specialty: str
    origin: str
    traits: tuple[str, ...] = ()  # an alien's two; an android's body
    skills: dict[str, SkillDie] = Field(default_factory=dict)  # keyed by the pack label
    credits: int = Field(default=STARTING_CREDITS, ge=0)
    items: dict[EntityId, Item] = Field(default_factory=dict)
    hindrances: tuple[str, ...] = ()  # the SRD's word: injuries and the like

    def die(self, skill: str) -> int:
        return self.skills.get(skill, DEFAULT_DIE)

    def rows(self) -> Rows:
        skills = ", ".join(f"{skill} d{die}" for skill, die in self.skills.items())
        return tuple(
            (label, value)
            for label, value in (
                ("Specialty", self.specialty),
                ("Origin", self.origin),
                ("Traits", ", ".join(self.traits)),
                ("Skills", skills),
                ("Credits", f"₡{self.credits}"),
                ("Hindrances", ", ".join(self.hindrances)),
            )
            if value
        )


TwentyfourxxWorld = SceneWorld[Person, Operator]


class TwentyfourxxCharacter(Mutable):
    specialty: str
    origin: str
    traits: tuple[str, ...] = ()
    skills: dict[str, SkillDie]
    items: tuple[Kit, ...]  # the comm, the specialty kit, Muscle's weapon


class TwentyfourxxGame(Game[TwentyfourxxWorld]):
    pass


class TwentyfourxxScenarioFile(Scenario[SceneCanon[Person]]):
    pass


class TwentyfourxxCharacterFile(Character[TwentyfourxxCharacter]):
    pass


def raised(current: SkillDie | None) -> SkillDie:
    """The SRD's advancement ladder: none -> d8 -> d10 -> d12."""
    if current is None:
        return LADDER[0]
    if current == LADDER[-1]:
        raise ValueError("the skill is already at d12")
    return LADDER[LADDER.index(current) + 1]


def player_operator(character: Character[TwentyfourxxCharacter]) -> Operator:
    """The played character as the world holds them; `new_game` and `preview_character` share it."""
    payload = character.payload
    taken: list[str] = []
    items: dict[EntityId, Item] = {}
    for kit in payload.items:
        key = slug(kit.name, taken)
        taken.append(key)
        items[EntityId(key)] = Item(name=kit.name, bulky=kit.bulky, breaks=kit.breaks)
    return Operator(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        specialty=payload.specialty,
        origin=payload.origin,
        traits=payload.traits,
        skills=payload.skills,
        items=items,
    )
