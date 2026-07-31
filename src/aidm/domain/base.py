import re
from collections.abc import Iterable
from typing import Annotated, Literal, NewType, get_args

from pydantic import Field

Role = Literal["director", "narrator", "maintainer", "creator"]
EngineId = Literal["story", "dnd5e"]
Kind = Literal["actor", "location", "item"]
EntityId = NewType("EntityId", str)
SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
Slug = Annotated[str, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=64)]

PLAYER_ID = EntityId("player")
ROLES: tuple[Role, ...] = get_args(Role)
ENGINE_IDS: tuple[EngineId, ...] = get_args(EngineId)
SAVE_VERSION = 19


def as_engine_id(value: str) -> EngineId:
    """Narrows a routed string; `EngineId` is closed, so an unknown one is a bug, not a choice."""
    for engine in ENGINE_IDS:
        if engine == value:
            return engine
    raise ValueError(f"unknown engine {value!r}")


def content_id(value: str) -> Slug:
    """Narrows a routed id before it names a directory, so `Slug` downstream is a fact."""
    if re.fullmatch(SLUG_PATTERN, value) is None:
        raise ValueError(f"invalid content id {value!r}")
    return value


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, number = EntityId(base), 2
    while candidate in used:
        candidate, number = EntityId(f"{base}_{number}"), number + 1
    return candidate
