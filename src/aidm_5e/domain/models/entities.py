from typing import Annotated, Literal

from pydantic import Field

from ...content.records.base import ContentRef
from ...utils.models import Frozen
from .base import EntityId
from .progression import Progression
from .stats import StatBlock


class EntityDetail(Frozen):
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
