"""CREATOR — fills in one entity requested by the Maintainer. Narrow input, narrow output."""

import re
from collections.abc import Iterable
from functools import cache

from pydantic_ai import Agent, NativeOutput

from ..domain.models import Entity, EntityDetail, GrowthRequest
from .llm import RETRIES, model

INSTRUCTIONS = """You flesh out ONE new element of a tabletop RPG world. Stay consistent with the \
scenario, with everything that already exists, and with the brief you are given. Contradict none \
of them.

`description` — two sentences of concrete, usable detail: for a person their look, manner and \
what they want; for a place what it looks like and who is found there; for an item what it looks \
like and what it does.
`hook` — one sentence on how this can matter to the player later.

The narration is what the player was just told about it; whatever it already says must stay true. \
The catalogue is everything that already exists, so you can place this element among it without \
repeating or contradicting anything.

Invent nothing beyond this single element — no other names, no plot twists."""


@cache
def agent() -> Agent[None, EntityDetail]:
    return Agent(
        model(),
        name="creator",
        output_type=NativeOutput(EntityDetail),
        instructions=INSTRUCTIONS,
        retries=RETRIES,
    )


def slug(name: str, taken: Iterable[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}_{n}", n + 1
    return candidate


async def create(prompt: str, request: GrowthRequest, taken: Iterable[str]) -> Entity:
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
