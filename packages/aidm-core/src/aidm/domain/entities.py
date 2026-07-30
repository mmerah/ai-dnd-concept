from typing import Annotated, Literal

from pydantic import Field

from ..utils.models import Frozen
from .base import EntityId, Kind
from .engine import EngineData


class EntityDetail(Frozen):
    description: str
    hook: str


class EntityDefinitionBase(Frozen):
    id: EntityId
    name: str
    brief: str
    known: bool = False
    engine_data: EngineData | None = None


class ActorDefinition(EntityDefinitionBase):
    kind: Literal["actor"] = "actor"
    location_id: EntityId


class ItemDefinition(EntityDefinitionBase):
    kind: Literal["item"] = "item"
    container_id: EntityId


class LocationDefinition(EntityDefinitionBase):
    kind: Literal["location"] = "location"


type EntityDefinition = Annotated[
    ActorDefinition | ItemDefinition | LocationDefinition,
    Field(discriminator="kind"),
]


class StartingItemDefinition(Frozen):
    name: str
    brief: str
    engine_data: EngineData | None = None


class BaseEntity(Frozen):
    id: EntityId
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False
    authored: bool = True
    rules: EngineData | None = None


class ActorEntity(BaseEntity):
    kind: Literal["actor"] = "actor"
    location_id: EntityId


class ItemEntity(BaseEntity):
    kind: Literal["item"] = "item"
    container_id: EntityId


class LocationEntity(BaseEntity):
    kind: Literal["location"] = "location"


type Entity = Annotated[ActorEntity | ItemEntity | LocationEntity, Field(discriminator="kind")]


def placement(kind: Kind, location_id: EntityId) -> dict[str, EntityId]:
    match kind:
        case "location":
            return {}
        case "actor":
            return {"location_id": location_id}
        case "item":
            return {"container_id": location_id}
