from pydantic import Field

from aidm.core.entities import CheckedEntityId
from aidm.engines.rooms.world import Dungeon, Dweller


class MapDraft[N: Dweller](Dungeon[N]):
    """A map: places, the ways between them, and the npcs and items in them."""

    start: CheckedEntityId = Field(description="Exact id of the place this map starts from.")
