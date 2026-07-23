"""The character, the scenario identity vs. live world, and the whole-game state that ties them."""

from typing import Self

from pydantic import Field, model_validator

from .base import SAVE_VERSION, EntityId, Frozen
from .entities import Entity, find


class Attributes(Frozen):
    strength: int = 10
    dexterity: int = 10
    intellect: int = 10
    wisdom: int = 10


class CharacterSheet(Frozen):
    """The on-disk character file: who they are, playable in any scenario. Deliberately has no
    location — where they start belongs to the scenario, whose entity ids a sheet cannot know."""

    name: str
    attributes: Attributes = Attributes()
    hp: int = 10
    max_hp: int = 10
    inventory: list[str] = Field(default_factory=list)


class Character(CharacterSheet):
    """A sheet placed in a world: the live character the reducer edits."""

    location_id: EntityId  # inventory stays names, because loose items have no entity to point at


class ScenarioMeta(Frozen):
    """Static scenario identity. Lives inside GameState and is never edited during play."""

    title: str
    premise: str


class WorldState(Frozen):
    """The live canon the reducer edits — everything discover/Maintainer/Creator touch."""

    entities: list[Entity] = Field(default_factory=list)


class ScenarioDef(Frozen):
    """The on-disk scenario file: static identity, starting canon, and where a character begins."""

    meta: ScenarioMeta
    starting_location_id: EntityId
    entities: list[Entity] = Field(default_factory=list)

    @model_validator(mode="after")
    def _starting_location_exists(self) -> Self:
        """Checked here so a malformed scenario fails at its own boundary, not mid-turn."""
        entity = find(self.entities, self.starting_location_id)
        if entity is None or entity.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        return self


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
