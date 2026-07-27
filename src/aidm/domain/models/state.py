"""The character sheet, the scenario identity vs. live world, and the state that ties them."""

from typing import Self

from pydantic import Field, model_validator

from ...utils.ids import slug
from .base import PLAYER_ID, SAVE_VERSION, EntityId, Frozen
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity, make_entity
from .stats import Attributes, StatBlock


class StartingItem(Frozen):
    """An item the character starts with, promoted to a canon item at composition."""

    name: str
    brief: str


class CharacterSheet(Frozen):
    """The on-disk character definition. The entity it seeds, not the sheet, owns values a leveling
    system later evolves."""

    name: str
    brief: str
    starting_attributes: Attributes = Attributes()
    starting_max_hp: int = 10
    starting_items: list[StartingItem] = Field(default_factory=list)


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
        # A scenario must place any character, not just one it names; the sheet supplies the player.
        if PLAYER_ID in ids:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
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
    scenario: ScenarioMeta
    world: WorldState
    history: list[Exchange] = Field(default_factory=list)
    turn: int = 0

    @property
    def player(self) -> ActorEntity:
        player = self.world.entities.get(PLAYER_ID)
        if not isinstance(player, ActorEntity):
            raise ValueError(f"the reserved id {PLAYER_ID!r} does not name an actor")
        return player

    @model_validator(mode="after")
    def _consistent_world(self) -> Self:
        """Positions and containment must agree, so lookups never lie: every actor stands in a real
        location, and every item is held by exactly one actor xor lies at one location."""
        entities = self.world.entities

        def is_location(entity_id: EntityId) -> bool:
            return isinstance(entities.get(entity_id), LocationEntity)

        # Unrevealed canon is offered as a `discover` target; the player must never be one.
        if not self.player.known:
            raise ValueError("the player entity must be known")

        held: list[EntityId] = []
        for actor in (e for e in entities.values() if isinstance(e, ActorEntity)):
            if not is_location(actor.location_id):
                raise ValueError(f"actor {actor.id!r} is not in a valid location")
            for item_id in actor.inventory:
                item = entities.get(item_id)
                if not isinstance(item, ItemEntity):
                    raise ValueError(f"{actor.id!r} holds {item_id!r}, which is not a canon item")
                if item.location_id is not None:
                    raise ValueError(f"held item {item_id!r} also lies at a location")
                held.append(item_id)
        duplicated = sorted({i for i in held if held.count(i) > 1})
        if duplicated:
            raise ValueError(f"items held in more than one inventory: {duplicated}")

        for item in (e for e in entities.values() if isinstance(e, ItemEntity)):
            if item.location_id is None and item.id not in held:
                raise ValueError(f"item {item.id!r} is held by no one and lies nowhere")
            if item.location_id is not None and not is_location(item.location_id):
                raise ValueError(f"item {item.id!r} lies in a non-location")
        return self

    @classmethod
    def from_scenario(cls, scenario: ScenarioDef, character: CharacterSheet) -> Self:
        """A sheet placed at the scenario's start, over its canon. Starting items become canon items
        held by the player (location None), so an inventory holds real ids, not free text."""
        entities = dict(scenario.as_world().entities)
        inventory: list[EntityId] = []
        for item in character.starting_items:
            entity = make_entity(
                "item",
                id=slug(item.name, entities.keys()),
                name=item.name,
                brief=item.brief,
                known=True,
                authored=True,
            )
            entities[entity.id] = entity
            inventory.append(entity.id)
        entities[PLAYER_ID] = ActorEntity(
            id=PLAYER_ID,
            name=character.name,
            brief=character.brief,
            known=True,
            location_id=scenario.starting_location_id,
            inventory=inventory,
            stats=StatBlock(
                attributes=character.starting_attributes,
                max_hp=character.starting_max_hp,
                hp=character.starting_max_hp,
            ),
        )
        return cls(scenario=scenario.meta, world=WorldState(entities=entities))
