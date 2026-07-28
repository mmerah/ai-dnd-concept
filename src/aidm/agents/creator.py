from collections.abc import Iterable

from pydantic_ai import NativeOutput

from ..domain.models import (
    ENTITY_ADAPTER,
    Entity,
    EntityDetail,
    EntityId,
    GrowthRequest,
    placement,
    slug,
)
from .llm import build_agent
from .prompts.creator import INSTRUCTIONS

agent = build_agent("creator", output_type=NativeOutput(EntityDetail), instructions=INSTRUCTIONS)


async def create(
    prompt: str, request: GrowthRequest, taken: Iterable[EntityId], location: EntityId
) -> Entity:
    detail = (await agent().run(prompt)).output
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
