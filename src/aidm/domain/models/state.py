"""The character, the scenario identity vs. live world, and the whole-game state that ties them."""

from pydantic import Field

from .base import SAVE_VERSION, Frozen
from .entities import Entity


class Attributes(Frozen):
    strength: int = 10
    dexterity: int = 10
    intellect: int = 10
    wisdom: int = 10


class Character(Frozen):
    name: str
    attributes: Attributes = Attributes()
    hp: int = 10
    max_hp: int = 10
    inventory: list[str] = Field(default_factory=list)
    location: str


class ScenarioMeta(Frozen):
    """Static scenario identity. Lives inside GameState and is never edited during play."""

    title: str
    premise: str


class WorldState(Frozen):
    """The live canon the reducer edits — everything discover/Maintainer/Creator touch."""

    entities: list[Entity] = Field(default_factory=list)


class ScenarioDef(Frozen):
    """The on-disk scenario file: static identity plus starting canon, no character."""

    meta: ScenarioMeta
    entities: list[Entity] = Field(default_factory=list)


class Exchange(Frozen):
    prompt: str
    narration: str


class GameState(Frozen):
    version: int = SAVE_VERSION
    character: Character
    scenario: ScenarioMeta
    world: WorldState
    history: list[Exchange] = Field(default_factory=list)
    turn: int = 0
