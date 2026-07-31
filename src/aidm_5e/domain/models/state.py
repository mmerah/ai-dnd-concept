from typing import Self

from pydantic import Field, model_validator

from aidm.utils.models import EMPTY_FROZEN_MAP

from ...content.records.base import ContentRef
from ...utils.models import Attributes, Frozen, updated
from .base import PLAYER_ID, SAVE_VERSION, EntityId, slug
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity
from .progression import Advancement, Decisions, Origin
from .stats import StatBlock


class StartingItem(Frozen):
    name: str
    brief: str
    ref: ContentRef | None = None


class CharacterSheet(Frozen):
    name: str
    brief: str
    origin: Origin
    starting_attributes: Attributes = Attributes()
    decisions: Decisions = EMPTY_FROZEN_MAP
    starting_items: tuple[StartingItem, ...] = ()


class ScenarioMeta(Frozen):
    title: str
    premise: str


class WorldState(Frozen):
    entities: dict[EntityId, Entity] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> Self:
        if wrong := [k for k, e in self.entities.items() if k != e.id]:
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
                held_by = self.container_of(entity)
                return held_by.id if isinstance(held_by, LocationEntity) else held_by.location_id

    def container_of(self, item: ItemEntity) -> ActorEntity | LocationEntity:
        container = self.entities.get(item.container_id)
        if not isinstance(container, ActorEntity | LocationEntity):
            raise ValueError(f"item {item.id!r} is in {item.container_id!r}, which holds nothing")
        return container

    def carried_by(self, actor_id: EntityId) -> list[ItemEntity]:
        return [
            e
            for e in self.entities.values()
            if isinstance(e, ItemEntity) and e.container_id == actor_id
        ]


class ScenarioDef(Frozen):
    meta: ScenarioMeta
    starting_location_id: EntityId
    entities: list[Entity] = Field(default_factory=list)

    @model_validator(mode="after")
    def _valid_scenario(self) -> Self:
        ids = [e.id for e in self.entities]
        if duplicates := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"scenario has duplicate entity ids: {duplicates}")
        if PLAYER_ID in ids:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        start = next((e for e in self.entities if e.id == self.starting_location_id), None)
        if start is None or start.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        return self


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
        entities = self.world.entities

        if not self.player.known:
            raise ValueError("the player entity must be known")
        if levelled := sorted(
            e.id
            for e in entities.values()
            if isinstance(e, ActorEntity) and e.progression is not None and e.id != PLAYER_ID
        ):
            raise ValueError(f"only the player may have progression: {levelled}")

        for actor in (e for e in entities.values() if isinstance(e, ActorEntity)):
            if not isinstance(entities.get(actor.location_id), LocationEntity):
                raise ValueError(f"actor {actor.id!r} is not in a valid location")
        for item in (e for e in entities.values() if isinstance(e, ItemEntity)):
            self.world.container_of(item)
        return self

    @classmethod
    def from_scenario(
        cls,
        scenario: ScenarioDef,
        character: CharacterSheet,
        start: Advancement,
    ) -> Self:
        entities = {entity.id: entity for entity in scenario.entities}
        for item in character.starting_items:
            entity = ItemEntity(
                id=slug(item.name, entities.keys()),
                name=item.name,
                brief=item.brief,
                ref=item.ref,
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
            stats=StatBlock(attributes=start.attributes, max_hp=start.hp_gain, hp=start.hp_gain),
            progression=start.progression,
        )
        return cls(scenario=scenario.meta, world=WorldState(entities=entities))
