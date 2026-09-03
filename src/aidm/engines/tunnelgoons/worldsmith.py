from pydantic import Field

from aidm.core.entities import CheckedEntityId, Frozen, Refusal
from aidm.core.model import ScenarioKind
from aidm.engines.hub import OFFER_ASK, Board, Campaign
from aidm.engines.tunnelgoons.world import Dungeon, MapCanon, TunnelGoonsWorld

MIN_PLACES = 4
MIN_EXTENSION_PLACES = 2
TAVERN_ASK = (
    "(no map yet — write the tavern: one known place, its keeper and regulars as npcs, no ways "
    "out, and a `board` of two or three offers; " + OFFER_ASK + ")"
)
JOB_BRIEF = (
    "The player is leaving {title} ({place}) on a job. WHAT THE PLAYER WANTS TO PURSUE is the job "
    "they take: an offer by its title, whose pitch THE BOARD holds, or their own words. Write the "
    "job as a whole new region joining the map at {place}: a complete dungeon by the opening "
    "map's bar, its start known and named after the offer, since the ledger lists the job by that "
    "name. Old dungeons stay on the map, so write only new ids; a job left open and taken again "
    "gets the part not yet walked."
)


class MapDraft(Dungeon):
    """The worldsmith's complete authored region: the map, and what stands and lies in it."""

    start: CheckedEntityId
    board: Board | None = None  # a campaign's opening tavern only


class ReturnDraft(Frozen):
    """The report at the tavern: the paragraph; `finished` is the open job's."""

    debrief: str = Field(min_length=1)
    offers: Board


def map_refusal(draft: MapDraft) -> str | None:
    unmet = _map_unmet(draft) + _board_unmet(draft)
    return None if not unmet else "the map needs " + "; ".join(unmet)


def hub_refusal(draft: MapDraft) -> str | None:
    unmet = _hub_unmet(draft)
    return None if not unmet else "the tavern needs " + "; ".join(unmet)


def job_refusal(draft: MapDraft, world: TunnelGoonsWorld) -> str | None:
    unmet = _map_unmet(draft) + _overlap_unmet(draft, world) + _board_unmet(draft)
    return None if not unmet else "the job's region needs " + "; ".join(unmet)


def extension_refusal(draft: MapDraft, world: TunnelGoonsWorld) -> str | None:
    unmet = _extension_unmet(draft) + _overlap_unmet(draft, world) + _board_unmet(draft)
    return None if not unmet else "the extension needs " + "; ".join(unmet)


def opening_canon(draft: MapDraft, source: str, kind: ScenarioKind) -> MapCanon:
    campaign = None
    if kind == "campaign":
        if draft.board is None:
            raise Refusal("a campaign's opening needs a board")
        campaign = Campaign(place=draft.start, board=draft.board)
    return MapCanon(
        places=draft.places,
        ways=draft.ways,
        npcs=draft.npcs,
        items=draft.items,
        start=draft.start,
        source=source,
        campaign=campaign,
    )


def _map_unmet(draft: MapDraft) -> list[str]:
    places = draft.places
    unmet: list[str] = []
    if len(places) < MIN_PLACES:
        unmet.append(f"{MIN_PLACES} or more places; the map has {len(places)}: {sorted(places)}")
    unmet.extend(_start_unmet(draft))
    if draft.start in places and not any(way.known for way in draft.ways.get(draft.start, ())):
        unmet.append("at least one known way out of the starting place")
    ways = [way for leaving in draft.ways.values() for way in leaving]
    if not any(not way.known for way in ways):
        unmet.append("at least one way starting unknown")
    if not any(way.locked for way in ways):
        unmet.append("at least one way starting locked")
    if not _has_hidden_thing(draft):
        unmet.append("at least one hidden npc or item")
    if not draft.has_shortcut():
        unmet.append("a shortcut with an alternate route")
    return unmet


def _hub_unmet(draft: MapDraft) -> list[str]:
    unmet = _start_unmet(draft)
    if draft.board is None:
        unmet.append("a `board` of two or three offers")
    return unmet


def _start_unmet(draft: MapDraft) -> list[str]:
    places = draft.places
    unmet: list[str] = []
    if draft.start not in places:
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if not places[draft.start].known:
            unmet.append("the starting place known to the player")
        if missing := sorted(set(places) - draft.reachable(draft.start)):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    return unmet


def _extension_unmet(draft: MapDraft) -> list[str]:
    places = draft.places
    unmet: list[str] = []
    if len(places) < MIN_EXTENSION_PLACES:
        unmet.append(
            f"{MIN_EXTENSION_PLACES} or more new places; the region has {len(places)}: "
            f"{sorted(places)}"
        )
    if draft.start not in places:
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if places[draft.start].known:
            unmet.append("a starting place hidden from the player")
        if missing := sorted(set(places) - draft.reachable(draft.start)):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    if not any(way for leaving in draft.ways.values() for way in leaving):
        unmet.append("ways connecting the new places")
    if not _has_hidden_thing(draft):
        unmet.append("at least one hidden npc or item")
    return unmet


def _overlap_unmet(draft: MapDraft, world: TunnelGoonsWorld) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []


def _board_unmet(draft: MapDraft) -> list[str]:
    if draft.board is not None:
        return ["no `board`: only a campaign's opening tavern carries one"]
    return []


def _has_hidden_thing(draft: MapDraft) -> bool:
    return any(not one.known for one in (*draft.npcs.values(), *draft.items.values()))
