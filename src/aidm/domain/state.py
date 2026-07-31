from collections.abc import Iterable
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm_5e.models import Dnd5eState
from aidm_story.models import StoryState

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap, updated
from .base import PLAYER_ID, EngineId, EntityId, slug
from .definitions import (
    ActorEngineData,
    CharacterDefinition,
    ItemEngineData,
    ScenarioDefinition,
    ScenarioMeta,
)
from .entities import ActorEntity, BaseEntity, Entity, ItemEntity, LocationEntity

type EngineState = Annotated[StoryState | Dnd5eState, Field(discriminator="engine")]
type EntityEngineData = ActorEngineData | ItemEngineData


class WorldState(Frozen):
    entities: FrozenMap[EntityId, Entity] = EMPTY_FROZEN_MAP

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        wrong = [key for key, entity in self.entities.items() if key != entity.id]
        if wrong:
            raise ValueError(f"entity keys disagree with their ids: {wrong}")
        return self

    def require(self, entity_id: EntityId) -> Entity:
        entity = self.entities.get(entity_id)
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

    def replacing(self, entity: Entity) -> Self:
        return updated(self, entities={**self.entities, entity.id: entity})

    def adding(self, entity: Entity) -> Self:
        if entity.id in self.entities:
            raise ValueError(f"entity id {entity.id!r} already exists")
        return self.replacing(entity)

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
        container = self.entities.get(item.container_id)
        if not isinstance(container, ActorEntity | LocationEntity):
            raise ValueError(f"item {item.id!r} is in {item.container_id!r}, which holds nothing")
        return container

    def carried_by(self, actor_id: EntityId) -> tuple[ItemEntity, ...]:
        return tuple(
            entity
            for entity in self.entities.values()
            if isinstance(entity, ItemEntity) and entity.container_id == actor_id
        )

    def ids_of(self, kind: type[BaseEntity]) -> set[EntityId]:
        return {entity.id for entity in self.entities.values() if isinstance(entity, kind)}


class Exchange(Frozen):
    prompt: str
    narration: str


class GameState(Frozen):
    save_version: int
    scenario: ScenarioMeta
    world: WorldState
    engine: EngineState
    history: tuple[Exchange, ...] = ()
    turn: int = Field(default=0, ge=0)

    @property
    def engine_id(self) -> EngineId:
        return self.engine.engine

    @property
    def player(self) -> ActorEntity:
        player = self.world.entities.get(PLAYER_ID)
        if not isinstance(player, ActorEntity):
            raise ValueError(f"the reserved id {PLAYER_ID!r} does not name an actor")
        return player

    @model_validator(mode="after")
    def _consistent_world(self) -> Self:
        entities = self.world.entities
        if not self.player.known:
            raise ValueError("the player entity must be known")
        for actor in (entity for entity in entities.values() if isinstance(entity, ActorEntity)):
            if not isinstance(entities.get(actor.location_id), LocationEntity):
                raise ValueError(f"actor {actor.id!r} is not in a valid location")
        for item in (entity for entity in entities.values() if isinstance(entity, ItemEntity)):
            self.world.container_of(item)
        _require_same_ids(self.engine.actors, self.world.ids_of(ActorEntity), "actor")
        _require_same_ids(self.engine.items, self.world.ids_of(ItemEntity), "item")
        return self


def _require_same_ids(held: Iterable[EntityId], expected: set[EntityId], kind: str) -> None:
    """Keep the engine side table from drifting once an entity is created or removed."""
    tracked = set(held)
    if tracked != expected:
        missing = sorted(expected - tracked)
        extra = sorted(tracked - expected)
        raise ValueError(
            f"engine {kind} state does not track the world: missing {missing}, unknown {extra}"
        )


class AuthoredWorld(Frozen):
    """The composed world alongside the authored engine data, keyed by the id each entity got."""

    world: WorldState
    engine_data: FrozenMap[EntityId, EntityEngineData] = EMPTY_FROZEN_MAP


def world_from_definitions(
    scenario: ScenarioDefinition,
    character: CharacterDefinition,
) -> AuthoredWorld:
    entities: dict[EntityId, Entity] = {}
    authored: dict[EntityId, EntityEngineData] = {}
    for definition in scenario.entities:
        match definition.kind:
            case "actor":
                entity = ActorEntity(
                    id=definition.id,
                    name=definition.name,
                    brief=definition.brief,
                    known=definition.known,
                    location_id=definition.location_id,
                )
            case "item":
                entity = ItemEntity(
                    id=definition.id,
                    name=definition.name,
                    brief=definition.brief,
                    known=definition.known,
                    container_id=definition.container_id,
                )
            case "location":
                entity = LocationEntity(
                    id=definition.id,
                    name=definition.name,
                    brief=definition.brief,
                    known=definition.known,
                )
        entities[entity.id] = entity
        if definition.kind != "location" and definition.engine_data is not None:
            authored[entity.id] = definition.engine_data
    for item in character.starting_items:
        entity = ItemEntity(
            id=slug(item.name, entities),
            name=item.name,
            brief=item.brief,
            known=True,
            container_id=PLAYER_ID,
        )
        entities[entity.id] = entity
        if item.engine_data is not None:
            authored[entity.id] = item.engine_data
    entities[PLAYER_ID] = ActorEntity(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        location_id=scenario.starting_location_id,
    )
    return AuthoredWorld(world=WorldState(entities=entities), engine_data=authored)
