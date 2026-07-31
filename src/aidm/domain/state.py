from collections.abc import Iterable
from typing import Annotated, Self

from pydantic import Field, model_validator

from aidm_5e.models import Dnd5eState
from aidm_story.models import StoryState

from ..utils.models import Frozen, Mutable
from .base import PLAYER_ID, EngineId, EntityId, Slug
from .definitions import Character, EntityEngineData, Scenario, ScenarioMeta
from .entities import ActorEntity, BaseEntity, Entity, ItemEntity, LocationEntity
from .facts import ActorMoved, CoreFact, EntityCreated, EntityDiscovered, ItemMoved

type EngineState = Annotated[StoryState | Dnd5eState, Field(discriminator="engine")]


class WorldState(Mutable):
    entities: dict[EntityId, Entity] = Field(default_factory=dict)

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


class GameState(Mutable):
    save_version: int
    scenario_id: Slug
    character_id: Slug
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

    def is_here(self, entity: Entity) -> bool:
        return self.world.location_of(entity) == self.player.location_id

    def draft(self) -> "GameState":
        """A working copy a resolution mutates; a failed turn never replaces the committed state."""
        return self.model_copy(deep=True)

    def committed(self) -> "GameState":
        """The one validation per transaction that replaces validating after every change."""
        return GameState.model_validate(self.model_dump(round_trip=True))

    def add(self, entity: Entity) -> EntityCreated:
        """Copy into the fact, so a later move in the same turn cannot rewrite the record."""
        if entity.id in self.world.entities:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self.world.entities[entity.id] = entity
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
    engine_data: dict[EntityId, EntityEngineData] = Field(default_factory=dict)


def authored_world(scenario: Scenario, character: Character) -> AuthoredWorld:
    player = ActorEntity(
        id=PLAYER_ID,
        name=character.name,
        brief=character.brief,
        known=True,
        location_id=scenario.world.starting_location_id,
    )
    entities: dict[EntityId, Entity] = {}
    for entity in (*scenario.world.entities, *character.profile.items, player):
        if entity.id in entities:
            raise ValueError(f"authored entity id {entity.id!r} appears twice")
        # Copy: the loaded files outlive the game, and entities are mutable now.
        entities[entity.id] = entity.model_copy(deep=True)
    return AuthoredWorld(
        world=WorldState(entities=entities),
        engine_data={
            **scenario.overlay.actors,
            **scenario.overlay.items,
            **character.overlay.items,
        },
    )
