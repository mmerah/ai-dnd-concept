"""CREATOR — fills in one entity requested by the Maintainer. Narrow input, narrow output."""

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
    """The kind is known only at runtime, so the entity is validated rather than constructed.
    An invented actor gets the default stat block — `engine/` owns better numbers."""
    detail = (await agent().run(prompt)).output
    # A grown actor/item appears in the scene just narrated, so it goes to the player's location.
    # It is known: the narrator already named it.
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
