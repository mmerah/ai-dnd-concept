from typing import Annotated, Literal

from pydantic import Field

from ..utils.models import Frozen
from .base import EntityId, Kind


class EntityDetail(Frozen):
    description: str
    hook: str


class BaseEntity(Frozen):
    id: EntityId
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False
    authored: bool = True


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
