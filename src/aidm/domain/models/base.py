import re
from collections.abc import Iterable
from typing import Literal, NewType, get_args

Role = Literal["director", "narrator", "maintainer", "creator"]

EntityId = NewType("EntityId", str)

PLAYER_ID = EntityId("player")

ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 14


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, n = EntityId(base), 2
    while candidate in used:
        candidate, n = EntityId(f"{base}_{n}"), n + 1
    return candidate
