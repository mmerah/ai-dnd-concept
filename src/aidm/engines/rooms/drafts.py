from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.engines.hub import Board
from aidm.engines.rooms.world import Dungeon, Dweller


class MapDraft[N: Dweller](Dungeon[N]):
    """The worldsmith's complete authored region: the map, and what stands and lies in it."""

    start: CheckedEntityId
    board: Board | None = None  # a campaign's opening tavern only


class ReturnDraft(Frozen):
    """The report at the tavern: the paragraph; `finished` is the open job's."""

    debrief: str = Field(min_length=1)
    offers: Board
