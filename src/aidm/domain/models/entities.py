from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from ...content.records.base import ContentRef
from ...utils.models import Frozen, Kind
from .base import EntityId
from .progression import Progression
from .stats import StatBlock


class EntityDetail(Frozen):
    """Creator-authored detail beyond a growth request."""

    description: str
    hook: str


class BaseEntity(Frozen):
    id: EntityId
    name: str
    brief: str
    ref: ContentRef | None = None
    detail: EntityDetail | None = None
    known: bool = False
    authored: bool = True


class ActorEntity(BaseEntity):
    kind: Literal["actor"] = "actor"
    location_id: EntityId
    stats: StatBlock = Field(default_factory=StatBlock)
    progression: Progression | None = None


class LocationEntity(BaseEntity):
    kind: Literal["location"] = "location"


class ItemEntity(BaseEntity):
    kind: Literal["item"] = "item"
    container_id: EntityId


Entity = Annotated[ActorEntity | LocationEntity | ItemEntity, Field(discriminator="kind")]

ENTITY_ADAPTER: TypeAdapter[Entity] = TypeAdapter(Entity)


def placement(kind: Kind, location_id: EntityId) -> dict[str, EntityId]:
    match kind:
        case "location":
            return {}
        case "actor":
            return {"location_id": location_id}
        case "item":
            return {"container_id": location_id}


class GrowthRequest(Frozen):
    kind: Kind
    name: str
    brief: str
    location: str | None = None


class Growth(Frozen):
    requests: list[GrowthRequest] = Field(default_factory=list)


GrowthRejectionReason = Literal["duplicate_name", "over_cap"]


class RejectedGrowth(Frozen):
    request: GrowthRequest
    reason: GrowthRejectionReason
