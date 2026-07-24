"""CREATOR — fills in one entity requested by the Maintainer. Narrow input, narrow output."""

import re
from collections.abc import Iterable

from pydantic_ai import NativeOutput

from ..domain.models import Entity, EntityDetail, EntityId, GrowthRequest
from .llm import build_agent
from .prompts.creator import INSTRUCTIONS

agent = build_agent("creator", output_type=NativeOutput(EntityDetail), instructions=INSTRUCTIONS)


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, n = EntityId(base), 2
    while candidate in used:
        candidate, n = EntityId(f"{base}_{n}"), n + 1
    return candidate


async def create(prompt: str, request: GrowthRequest, taken: Iterable[EntityId]) -> Entity:
    detail = (await agent().run(prompt)).output
    return Entity(
        id=slug(request.name, taken),
        kind=request.kind,
        name=request.name,
        brief=request.brief,
        detail=detail,
        known=True,  # the player already heard about it
        authored=False,
    )
