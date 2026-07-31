import re
from collections.abc import Iterable
from typing import Annotated, Literal, NewType, get_args

from pydantic import Field

Role = Literal["director", "narrator", "maintainer", "creator"]
EngineId = Literal["story", "dnd5e"]
Kind = Literal["actor", "location", "item"]
EntityId = NewType("EntityId", str)
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]

PLAYER_ID = EntityId("player")
ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 18


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, number = EntityId(base), 2
    while candidate in used:
        candidate, number = EntityId(f"{base}_{number}"), number + 1
    return candidate
