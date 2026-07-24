"""CREATOR — fills in one entity requested by the Maintainer. Narrow input, narrow output."""

from collections.abc import Iterable

from pydantic_ai import NativeOutput

from ..domain.models import Entity, EntityDetail, EntityId, GrowthRequest
from ..utils.ids import slug
from .llm import build_agent
from .prompts.creator import INSTRUCTIONS

agent = build_agent("creator", output_type=NativeOutput(EntityDetail), instructions=INSTRUCTIONS)


async def create(prompt: str, request: GrowthRequest, taken: Iterable[EntityId]) -> Entity:
    detail = (await agent().run(prompt)).output
    # Entity created is already known by the player since the narrator mentioned it
    return Entity(
        id=slug(request.name, taken),
        kind=request.kind,
        name=request.name,
        brief=request.brief,
        detail=detail,
        known=True,
        authored=False,
    )
