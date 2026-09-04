from typing import Annotated

from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen
from aidm.engines.hub import MIN_RECAP, MIN_SUMMARY, Board
from aidm.engines.rooms.world import Dungeon, Dweller


class MapDraft[N: Dweller](Dungeon[N]):
    """The worldsmith's complete authored region: the map, and what stands and lies in it."""

    start: CheckedEntityId
    board: Board | None = None  # a campaign's opening tavern only


class ReturnDraft(Frozen):
    """The report at the tavern: the paragraph; `finished` is the open job's.

    One answer, two readers: debrief and offers are the player's; summary and recaps are not.
    Leaks in play make this two spawns.
    """

    debrief: str = Field(min_length=1, description="One paragraph on the job, for the player.")
    offers: Board = Field(description="The board as it stands now, for the player.")
    summary: str = Field(
        min_length=MIN_SUMMARY,
        description="One paragraph on the job, in the third person, for the game master and for "
        "you, never the player: what was done, what was left undone, who was met and how it "
        "stands with them, what is owed, what was learned and what is still hidden.",
    )
    recaps: dict[CheckedEntityId, Annotated[str, Field(min_length=MIN_RECAP)]] = Field(
        description="One paragraph per place walked on this job, keyed by place id, for the "
        "game master and for you, never the player."
    )
