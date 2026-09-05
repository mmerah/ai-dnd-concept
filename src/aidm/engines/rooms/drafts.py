from aidm.core.entities import CheckedEntityId
from aidm.engines.rooms.world import Dungeon, Dweller


class MapDraft[N: Dweller](Dungeon[N]):
    """The worldsmith's complete authored region: the map, and what stands and lies in it."""

    start: CheckedEntityId
