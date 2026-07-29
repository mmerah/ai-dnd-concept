from collections.abc import Iterable

from ..domain.models.base import EntityId, slug
from ..domain.models.entities import ENTITY_ADAPTER, Entity, GrowthRequest, placement
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
