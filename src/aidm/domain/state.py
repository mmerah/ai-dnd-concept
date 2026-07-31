from collections.abc import Mapping
from typing import Self

from pydantic import Field, model_validator

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap, updated
from .base import PLAYER_ID, EngineId, EntityId, slug
from .definitions import CharacterDefinition, ScenarioDefinition, ScenarioMeta
from .engine import EngineData, require_engine
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity


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


class Exchange(Frozen):
    prompt: str
    narration: str


class GameState(Frozen):
    save_version: int
    engine: EngineId
    scenario: ScenarioMeta
    world: WorldState
    rules: EngineData
    history: tuple[Exchange, ...] = ()
    turn: int = Field(default=0, ge=0)

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
        require_engine(self.rules, self.engine, "game rules")
        for entity in entities.values():
            if entity.rules is not None:
                require_engine(entity.rules, self.engine, f"entity {entity.id!r} rules")
        return self


def world_from_definitions(
    scenario: ScenarioDefinition,
    character: CharacterDefinition,
) -> WorldState:
    entities: dict[EntityId, Entity] = {}
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
    for item in character.starting_items:
        entity = ItemEntity(
            id=slug(item.name, entities),
            name=item.name,
            brief=item.brief,
            known=True,
            container_id=PLAYER_ID,
        )
        entities[entity.id] = entity
    entities[PLAYER_ID] = ActorEntity(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        location_id=scenario.starting_location_id,
    )
    return WorldState(entities=entities)


def attach_initial_rules(
    world: WorldState,
    entity_rules: Mapping[EntityId, EngineData | None],
    engine: EngineId,
) -> WorldState:
    unknown = sorted(set(entity_rules) - set(world.entities))
    if unknown:
        raise ValueError(f"engine initialization named unknown entity ids: {unknown}")
    entities: dict[EntityId, Entity] = {}
    for entity_id, entity in world.entities.items():
        rules = entity_rules.get(entity_id)
        if rules is not None:
            require_engine(rules, engine, f"initial rules for entity {entity_id!r}")
        entities[entity_id] = updated(entity, rules=rules)
    return WorldState(entities=entities)
