"""The domain's own vocabularies. The frozen base and the 5e ability names live in
`utils/models.py` instead, because `content/` needs them and must not import `domain/`."""

from typing import Literal, NewType, get_args

Kind = Literal["actor", "location", "item"]
Role = Literal["director", "narrator", "maintainer", "creator"]

# Branded so a location or item name can never be passed where an entity id is expected.
EntityId = NewType("EntityId", str)

# The player is an actor entity like any other, under one reserved id so events, inventories and
# positions name them the same way they name anyone. No scenario entity may claim it (state.py).
PLAYER_ID = EntityId("player")

ROLES: tuple[Role, ...] = get_args(Role)
SAVE_VERSION = 10
