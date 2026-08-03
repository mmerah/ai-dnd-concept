from collections.abc import Iterator
from typing import Self

from pydantic import Field, JsonValue, model_validator

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
from .facts import CORE, Fact


class Record[T: Entity](Mutable):
    entity: T
    # Opaque here on purpose: the selected engine validates and rewrites its own payload.
    rules: dict[str, JsonValue] = Field(default_factory=dict)


ActorRecord = Record[ActorEntity]
ItemRecord = Record[ItemEntity]


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

    def add(self, entity: Entity, rules: dict[str, JsonValue]) -> Fact:
        """Copy into the fact, so a later move in the same turn cannot rewrite the record."""
        if self.world.find(entity.id) is not None:
            raise ValueError(f"entity id {entity.id!r} already exists")
        match entity:
            case ActorEntity():
                self.world.actors[entity.id] = ActorRecord(entity=entity, rules=rules)
            case ItemEntity():
                self.world.items[entity.id] = ItemRecord(entity=entity, rules=rules)
            case LocationEntity():
                if rules:
                    raise ValueError(f"location {entity.id!r} cannot carry engine rules")
                self.world.locations[entity.id] = entity
        summary = f"new {entity.kind}: {entity.name}"
        return Fact(
            source=CORE,
            kind="entity_created",
            trace=summary,
            narrator=summary,
            data={"entity_id": entity.id, "kind": entity.kind, "name": entity.name},
        )

    def reveal(self, entity: Entity) -> list[Fact]:
        if entity.known:
            return []
        entity.known = True
        summary = f"learned of {entity.name}"
        return [
            Fact(
                source=CORE,
                kind="entity_discovered",
                trace=summary,
                narrator=summary,
                data={"entity_id": entity.id, "name": entity.name},
            )
        ]

    def move_actor(self, actor: ActorEntity, destination: LocationEntity) -> Fact:
        actor.location_id = destination.id
        summary = f"{actor.name} moved to {destination.name}"
        return Fact(
            source=CORE,
            kind="actor_moved",
            trace=summary,
            narrator=summary,
            data={
                "actor_id": actor.id,
                "actor_name": actor.name,
                "location_id": destination.id,
                "location_name": destination.name,
            },
        )

    def move_item(self, item: ItemEntity, destination: ActorEntity | LocationEntity) -> Fact:
        item.container_id = destination.id
        to_actor = isinstance(destination, ActorEntity)
        if destination.id == PLAYER_ID:
            summary = f"took {item.name}"
        elif to_actor:
            summary = f"gave {item.name} to {destination.name}"
        else:
            summary = f"left {item.name} at {destination.name}"
        return Fact(
            source=CORE,
            kind="item_moved",
            trace=summary,
            narrator=summary,
            data={
                "item_id": item.id,
                "item_name": item.name,
                "to_id": destination.id,
                "to_name": destination.name,
                "to_kind": "actor" if to_actor else "location",
            },
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
        return self


class EngineRecords[A: Mutable, I: Mutable]:
    """Cached so two mechanics mutate one payload; `commit` flushes back only what it handed out."""

    def __init__(self, state: GameState, actor_state: type[A], item_state: type[I]) -> None:
        self.state = state
        self._actor_state = actor_state
        self._item_state = item_state
        self._actors: dict[EntityId, A] = {}
        self._items: dict[EntityId, I] = {}

    def actor(self, actor_id: EntityId) -> tuple[ActorEntity, A]:
        record = self.state.world.actor(actor_id)
        payload = self._actors.get(actor_id)
        if payload is None:
            payload = self._actor_state.model_validate(record.rules)
            self._actors[actor_id] = payload
        return record.entity, payload

    def item(self, item_id: EntityId) -> tuple[ItemEntity, I]:
        record = self.state.world.item(item_id)
        payload = self._items.get(item_id)
        if payload is None:
            payload = self._item_state.model_validate(record.rules)
            self._items[item_id] = payload
        return record.entity, payload

    def player(self) -> tuple[ActorEntity, A]:
        return self.actor(PLAYER_ID)

    def commit(self) -> GameState:
        for actor_id, payload in self._actors.items():
            self.state.world.actor(actor_id).rules = payload.model_dump(mode="json")
        for item_id, payload in self._items.items():
            self.state.world.item(item_id).rules = payload.model_dump(mode="json")
        return self.state.committed()
