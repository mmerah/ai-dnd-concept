"""The domain's own vocabularies. The frozen base and the 5e ability names live in
`utils/models.py` instead, because `content/` needs them and must not import `domain/`."""

import re
from collections.abc import Iterable
from typing import Literal, NewType, get_args

Kind = Literal["actor", "location", "item"]
Role = Literal["director", "narrator", "maintainer", "creator"]

# Branded so a location or item name can never be passed where an entity id is expected.
EntityId = NewType("EntityId", str)

# The player is an actor entity like any other, under one reserved id so events, inventories and
# positions name them the same way they name anyone. No scenario entity may claim it (state.py).
PLAYER_ID = EntityId("player")

ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 12


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    """Deterministic id-minting: a name becomes a unique, stable EntityId."""
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, n = EntityId(base), 2
    while candidate in used:
        candidate, n = EntityId(f"{base}_{n}"), n + 1
    return candidate
