from collections.abc import Iterator
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm.engines.dnd5e.state import (
    Dnd5eActorDefinition,
    Dnd5eActorState,
    Dnd5eCharacterData,
    Dnd5eItemDefinition,
    Dnd5eItemState,
)
from aidm.engines.story.state import (
    StoryActorDefinition,
    StoryActorState,
    StoryCharacterData,
    StoryItemDefinition,
    StoryItemState,
)

from .base import (
    PLAYER_ID,
    ActorEntity,
    EngineId,
    Entity,
    EntityId,
    Frozen,
    ItemEntity,
    Kind,
    LocationEntity,
    Mutable,
    Slug,
)
from .facts import ActorMoved, CoreFact, EntityCreated, EntityDiscovered, ItemMoved

type ActorRules = Annotated[StoryActorState | Dnd5eActorState, Field(discriminator="engine")]
type ItemRules = Annotated[StoryItemState | Dnd5eItemState, Field(discriminator="engine")]
type EntityRules = ActorRules | ItemRules
type ActorEngineData = Annotated[
    StoryActorDefinition | Dnd5eActorDefinition,
    Field(discriminator="engine"),
]
type ItemEngineData = Annotated[
    StoryItemDefinition | Dnd5eItemDefinition,
    Field(discriminator="engine"),
]
type CharacterEngineData = Annotated[
    StoryCharacterData | Dnd5eCharacterData,
    Field(discriminator="engine"),
]
type EntityEngineData = ActorEngineData | ItemEngineData
type EngineData = EntityEngineData | CharacterEngineData


def for_engine[T: EngineData](data: EngineData, expected: type[T]) -> T:
    """Tags are checked once at load, so a mismatch here means the wrong engine is resolving."""
    if not isinstance(data, expected):
        raise ValueError(f"authored data is {data.engine!r}, not {expected.__name__}")
    return data


def for_engine_or_none[T: EngineData](data: EngineData | None, expected: type[T]) -> T | None:
    return None if data is None else for_engine(data, expected)


class ActorRecord(Mutable):
    entity: ActorEntity
    rules: ActorRules


class ItemRecord(Mutable):
    entity: ItemEntity
    rules: ItemRules


class WorldState(Mutable):
    actors: dict[EntityId, ActorRecord] = Field(default_factory=dict)
    items: dict[EntityId, ItemRecord] = Field(default_factory=dict)
    locations: dict[EntityId, LocationEntity] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        mismatched = sorted(key for key, entity in self._entries() if key != entity.id)
        if mismatched:
            raise ValueError(f"entity keys disagree with their ids: {mismatched}")
        keys = [key for key, _ in self._entries()]
        if len(keys) != len(set(keys)):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise ValueError(f"entity ids appear under more than one kind: {duplicates}")
        return self

    def entities(self) -> Iterator[Entity]:
        return (entity for _, entity in self._entries())

    def all_ids(self) -> set[EntityId]:
        return {key for key, _ in self._entries()}

    def find(self, entity_id: EntityId) -> Entity | None:
        actor = self.actors.get(entity_id)
        if actor is not None:
            return actor.entity
        item = self.items.get(entity_id)
        if item is not None:
            return item.entity
        return self.locations.get(entity_id)

    def require(self, entity_id: EntityId) -> Entity:
        entity = self.find(entity_id)
        if entity is None:
            raise ValueError(f"unknown entity id {entity_id!r}")
        return entity

    def require_kind[T: Entity](self, entity_id: EntityId, expected: type[T]) -> T:
        entity = self.require(entity_id)
        if not isinstance(entity, expected):
            raise ValueError(
                f"used {entity_id!r} as {expected.__name__}, but it is a {entity.kind}"
            )
        return entity

    def actor(self, entity_id: EntityId) -> ActorRecord:
        record = self.actors.get(entity_id)
        if record is None:
            raise self._no_record(entity_id, "actor")
        return record

    def item(self, entity_id: EntityId) -> ItemRecord:
        record = self.items.get(entity_id)
        if record is None:
            raise self._no_record(entity_id, "item")
        return record

    def location_of(self, entity: Entity) -> EntityId | None:
        match entity:
            case LocationEntity():
                return None
            case ActorEntity():
                return entity.location_id
            case ItemEntity():
                container = self.container_of(entity)
                return (
                    container.id if isinstance(container, LocationEntity) else container.location_id
                )

    def container_of(self, item: ItemEntity) -> ActorEntity | LocationEntity:
        container = self.find(item.container_id)
        if not isinstance(container, ActorEntity | LocationEntity):
            raise ValueError(f"item {item.id!r} is in {item.container_id!r}, which holds nothing")
        return container

    def carried_by(self, actor_id: EntityId) -> tuple[ItemRecord, ...]:
        return tuple(
            record for record in self.items.values() if record.entity.container_id == actor_id
        )

    def _entries(self) -> Iterator[tuple[EntityId, Entity]]:
        """Places, then people, then things: prompt catalogues read in this order."""
        yield from self.locations.items()
        for key, actor in self.actors.items():
            yield key, actor.entity
        for key, item in self.items.items():
            yield key, item.entity

    def _no_record(self, entity_id: EntityId, kind: Kind) -> ValueError:
        entity = self.find(entity_id)
        if entity is None:
            return ValueError(f"unknown entity id {entity_id!r}")
        return ValueError(f"used {entity_id!r} as {kind}, but it is a {entity.kind}")


class Exchange(Frozen):
    prompt: str
    narration: str


class ScenarioMeta(Frozen):
    title: str
    premise: str


class GameState(Mutable):
    save_version: int
    scenario_id: Slug
    character_id: Slug
    scenario: ScenarioMeta
    engine: EngineId
    world: WorldState
    history: tuple[Exchange, ...] = ()
    turn: int = Field(default=0, ge=0)

    @property
    def player(self) -> ActorEntity:
        record = self.world.actors.get(PLAYER_ID)
        if record is None:
            raise ValueError(f"the reserved id {PLAYER_ID!r} does not name an actor")
        return record.entity

    def is_here(self, entity: Entity) -> bool:
        return self.world.location_of(entity) == self.player.location_id

    def draft(self) -> "GameState":
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return self.model_copy(deep=True)

    def committed(self) -> "GameState":
        """The one validation per transaction that replaces validating after every change."""
        return GameState.model_validate(self.model_dump(round_trip=True))

    def add(self, entity: Entity, rules: EntityRules | None) -> EntityCreated:
        """Copy into the fact, so a later move in the same turn cannot rewrite the record."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        if rules is not None and rules.engine != self.engine:
            raise ValueError(f"{entity.id!r} takes {rules.engine!r} rules in {self.engine!r}")
        if isinstance(entity, ActorEntity) and isinstance(rules, StoryActorState | Dnd5eActorState):
            self.world.actors[entity.id] = ActorRecord(entity=entity, rules=rules)
        elif isinstance(entity, ItemEntity) and isinstance(rules, StoryItemState | Dnd5eItemState):
            self.world.items[entity.id] = ItemRecord(entity=entity, rules=rules)
        elif isinstance(entity, LocationEntity) and rules is None:
            self.world.locations[entity.id] = entity
        else:
            raise ValueError(f"{entity.kind} {entity.id!r} cannot take {type(rules).__name__}")
        return EntityCreated(entity=entity.model_copy(deep=True))

    def reveal(self, entity: Entity) -> list[CoreFact]:
        if entity.known:
            return []
        entity.known = True
        return [EntityDiscovered(entity_id=entity.id, name=entity.name)]

    def move_actor(self, actor: ActorEntity, destination: LocationEntity) -> ActorMoved:
        actor.location_id = destination.id
        return ActorMoved(
            actor_id=actor.id,
            actor_name=actor.name,
            location_id=destination.id,
            location_name=destination.name,
        )

    def move_item(self, item: ItemEntity, destination: ActorEntity | LocationEntity) -> ItemMoved:
        item.container_id = destination.id
        return ItemMoved(
            item_id=item.id,
            item_name=item.name,
            to_id=destination.id,
            to_name=destination.name,
            to_kind="actor" if isinstance(destination, ActorEntity) else "location",
        )

    @model_validator(mode="after")
    def _consistent_world(self) -> Self:
        world = self.world
        if not self.player.known:
            raise ValueError("the player entity must be known")
        for record in world.actors.values():
            if record.entity.location_id not in world.locations:
                raise ValueError(f"actor {record.entity.id!r} is not in a valid location")
        for record in world.items.values():
            _ = world.container_of(record.entity)
        _require_one_engine(world, self.engine)
        return self


def _require_one_engine(world: WorldState, engine: EngineId) -> None:
    """A per-record tag makes a mixed world representable, so only this keeps it out."""
    foreign = sorted(
        [record.entity.id for record in world.actors.values() if record.rules.engine != engine]
        + [record.entity.id for record in world.items.values() if record.rules.engine != engine]
    )
    if foreign:
        raise ValueError(f"records hold rules from another engine than {engine!r}: {foreign}")
