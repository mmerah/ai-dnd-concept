"""The character, the scenario identity vs. live world, and the whole-game state that ties them."""

from typing import Self

from pydantic import Field, model_validator

from .base import SAVE_VERSION, EntityId, Frozen
from .entities import Entity


class Attributes(Frozen):
    strength: int = 10
    dexterity: int = 10
    intellect: int = 10
    wisdom: int = 10


class CharacterSheet(Frozen):
    """The on-disk character file: who they are, playable in any scenario."""

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
    """The live canon the reducer edits — everything discover/Maintainer/Creator touch.

    Keyed by id so uniqueness is a guarantee, not an assumption; `Entity.id` is kept because an
    entity travels standalone (through `EntityCreated`, `Turn.created`, `create()`'s return)."""

    entities: dict[EntityId, Entity] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        """The id is stored twice after a JSON round-trip; a mismatch would make lookups lie."""
        wrong = [k for k, e in self.entities.items() if k != e.id]
        if wrong:
            raise ValueError(f"entity keys disagree with their ids: {wrong}")
        return self


class ScenarioDef(Frozen):
    """The on-disk scenario file: static identity, starting canon, and where a character begins.
    Entities stay a JSON array — a list is the natural authoring shape; `as_world` keys them."""

    meta: ScenarioMeta
    starting_location_id: EntityId
    entities: list[Entity] = Field(default_factory=list)

    @model_validator(mode="after")
    def _valid_scenario(self) -> Self:
        """Checked here so a malformed scenario fails at its own boundary, not mid-turn."""
        ids = [e.id for e in self.entities]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"scenario has duplicate entity ids: {duplicates}")
        start = next((e for e in self.entities if e.id == self.starting_location_id), None)
        if start is None or start.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        return self

    def as_world(self) -> WorldState:
        return WorldState(entities={e.id: e for e in self.entities})


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

    @classmethod
    def from_scenario(cls, scenario: ScenarioDef, character: CharacterSheet) -> Self:
        """Compose a starting state: a sheet placed at the scenario's start, over its canon."""
        placed = Character(**character.model_dump(), location_id=scenario.starting_location_id)
        return cls(character=placed, scenario=scenario.meta, world=scenario.as_world())
