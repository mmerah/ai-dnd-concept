from collections.abc import Iterable

from ..domain.models import (
    ENTITY_ADAPTER,
    Entity,
    EntityId,
    GrowthRequest,
    placement,
    slug,
)
from .stages import CREATOR


async def create(
    prompt: str, request: GrowthRequest, taken: Iterable[EntityId], location: EntityId
) -> Entity:
    detail = await CREATOR.run(prompt, None)
    return ENTITY_ADAPTER.validate_python(
        {
            "kind": request.kind,
            "id": slug(request.name, taken),
            "name": request.name,
            "brief": request.brief,
            "detail": detail,
            "known": True,
            "authored": False,
            **placement(request.kind, location),
        }
    )
