"""Canon entities, the requests to grow them, and the lookups over a plain entity sequence."""

from collections.abc import Sequence

from pydantic import Field

from .base import EntityId, Frozen, Kind


class EntityDetail(Frozen):
    """What a Creator adds on top of a growth request."""

    description: str
    hook: str


class Entity(Frozen):
    id: EntityId
    kind: Kind
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False  # revealed to the player; unknown entities are Director-only canon
    authored: bool = True  # False once a Creator invented it mid-play


class GrowthRequest(Frozen):
    kind: Kind
    name: str
    brief: str


class Growth(Frozen):
    requests: list[GrowthRequest] = Field(default_factory=list)


def known(entities: Sequence[Entity]) -> list[Entity]:
    return [e for e in entities if e.known]


def hidden(entities: Sequence[Entity]) -> list[Entity]:
    return [e for e in entities if not e.known]


def find(entities: Sequence[Entity], entity_id: EntityId) -> Entity | None:
    return next((e for e in entities if e.id == entity_id), None)
