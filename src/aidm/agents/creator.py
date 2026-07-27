"""CREATOR — fills in one entity requested by the Maintainer. Narrow input, narrow output."""

from collections.abc import Iterable

from pydantic_ai import NativeOutput

from ..domain.models import Entity, EntityDetail, EntityId, GrowthRequest, make_entity
from ..utils.ids import slug
from .llm import build_agent
from .prompts.creator import INSTRUCTIONS

agent = build_agent("creator", output_type=NativeOutput(EntityDetail), instructions=INSTRUCTIONS)


async def create(
    prompt: str, request: GrowthRequest, taken: Iterable[EntityId], location: EntityId
) -> Entity:
    detail = (await agent().run(prompt)).output
    # A grown actor/item appears in the scene just narrated, so it goes to the player's location
    # (`location` is ignored for a grown location). It is known: the narrator already named it.
    return make_entity(
        request.kind,
        id=slug(request.name, taken),
        name=request.name,
        brief=request.brief,
        location_id=location,
        detail=detail,
        known=True,
        authored=False,
    )
