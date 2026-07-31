from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm_5e.models import Dnd5eActorDefinition, Dnd5eCharacterData, Dnd5eItemDefinition
from aidm_story.models import StoryActorDefinition, StoryCharacterData, StoryItemDefinition

from ..utils.models import Frozen
from .base import PLAYER_ID, EngineId, EntityId

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
type EngineData = ActorEngineData | ItemEngineData | CharacterEngineData


def for_engine[T: EngineData](data: EngineData, expected: type[T]) -> T:
    """Tags are checked once at load, so a mismatch here means the wrong engine is resolving."""
    if not isinstance(data, expected):
        raise ValueError(f"authored data is {data.engine!r}, not {expected.__name__}")
    return data


def for_engine_or_none[T: EngineData](data: EngineData | None, expected: type[T]) -> T | None:
    return None if data is None else for_engine(data, expected)


class ScenarioMeta(Frozen):
    title: str
    premise: str


class EntityDefinitionBase(Frozen):
    id: EntityId
    name: str
    brief: str
    known: bool = False


class ActorDefinition(EntityDefinitionBase):
    kind: Literal["actor"] = "actor"
    location_id: EntityId
    engine_data: ActorEngineData | None = None


class ItemDefinition(EntityDefinitionBase):
    kind: Literal["item"] = "item"
    container_id: EntityId
    engine_data: ItemEngineData | None = None


class LocationDefinition(EntityDefinitionBase):
    kind: Literal["location"] = "location"


type EntityDefinition = Annotated[
    ActorDefinition | ItemDefinition | LocationDefinition,
    Field(discriminator="kind"),
]


class StartingItemDefinition(Frozen):
    name: str
    brief: str
    engine_data: ItemEngineData | None = None


class CharacterDefinition(Frozen):
    name: str
    brief: str
    engine_data: CharacterEngineData
    starting_items: tuple[StartingItemDefinition, ...] = ()

    @property
    def engine(self) -> EngineId:
        return self.engine_data.engine


class ScenarioDefinition(Frozen):
    meta: ScenarioMeta
    engine: EngineId
    starting_location_id: EntityId
    entities: tuple[EntityDefinition, ...] = ()

    @model_validator(mode="after")
    def _valid_topology(self) -> Self:
        by_id = {entity.id: entity for entity in self.entities}
        if len(by_id) != len(self.entities):
            ids = [entity.id for entity in self.entities]
            duplicates = sorted({entity_id for entity_id in ids if ids.count(entity_id) > 1})
            raise ValueError(f"scenario has duplicate entity ids: {duplicates}")
        if PLAYER_ID in by_id:
            raise ValueError(f"an entity claims the reserved player id {PLAYER_ID!r}")
        starting_location = by_id.get(self.starting_location_id)
        if starting_location is None or starting_location.kind != "location":
            raise ValueError(
                f"starting_location_id {self.starting_location_id!r} is not a location here"
            )
        for entity in self.entities:
            if entity.kind == "actor":
                container = by_id.get(entity.location_id)
                if container is None or container.kind != "location":
                    raise ValueError(f"actor {entity.id!r} is not in a scenario location")
            elif entity.kind == "item":
                container = by_id.get(entity.container_id)
                if container is None or container.kind not in ("actor", "location"):
                    raise ValueError(f"item {entity.id!r} has no valid scenario container")
        return self


def validate_definition_engines(
    scenario: ScenarioDefinition,
    character: CharacterDefinition,
    engine: EngineId,
) -> None:
    authored = [
        ("scenario", scenario.engine),
        ("character", character.engine),
        *[
            (f"scenario entity {entity.id!r} engine_data", entity.engine_data.engine)
            for entity in scenario.entities
            if entity.kind != "location" and entity.engine_data is not None
        ],
        *[
            (f"starting item {item.name!r} engine_data", item.engine_data.engine)
            for item in character.starting_items
            if item.engine_data is not None
        ],
    ]
    for purpose, declared in authored:
        if declared != engine:
            raise ValueError(f"{purpose} engine is {declared!r}, selected engine is {engine!r}")
