from aidm.core.entities import CheckedEntityId
from aidm.engines.rooms.world import Dungeon, Dweller


class MapDraft[N: Dweller](Dungeon[N]):
    start: CheckedEntityId
