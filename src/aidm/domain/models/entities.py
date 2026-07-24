"""Canon entities, the requests to grow them, and the lookups over the live entity map."""

from collections.abc import Mapping
from typing import Literal

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
    known: bool = False  # revealed to the player
    authored: bool = True  # False once a Creator invented it mid-play


class GrowthRequest(Frozen):
    kind: Kind
    name: str
    brief: str


class Growth(Frozen):
    requests: list[GrowthRequest] = Field(default_factory=list)


# `duplicate_name`: a name that already exists; `over_cap`: admissible but beyond the turn's budget.
GrowthRejectionReason = Literal["duplicate_name", "over_cap"]


class RejectedGrowth(Frozen):
    """A growth request screening refused, with why — kept so the trace shows every drop."""

    request: GrowthRequest
    reason: GrowthRejectionReason


def known(entities: Mapping[EntityId, Entity]) -> list[Entity]:
    return [e for e in entities.values() if e.known]


def hidden(entities: Mapping[EntityId, Entity]) -> list[Entity]:
    return [e for e in entities.values() if not e.known]


def find(entities: Mapping[EntityId, Entity], entity_id: EntityId) -> Entity | None:
    return entities.get(entity_id)
