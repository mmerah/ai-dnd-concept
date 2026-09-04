from collections.abc import Sequence

from pydantic import BaseModel

from aidm.core.play import Commission
from aidm.core.tools import schema_text
from aidm.core.views import Sections, sections
from aidm.engines.base import Person
from aidm.engines.hub import OFFER_ASK, named_unmet
from aidm.engines.rooms.drafts import ItemDraft, MapDraft, NpcDraft, ReturnDraft
from aidm.engines.rooms.world import Dungeon, Dweller, RoomWorld

MIN_PLACES = 4
MIN_EXTENSION_PLACES = 2
MAP_ASK = "Write the opening map."
TAVERN_ASK = (
    "Write the tavern: one known place, its keeper and regulars as npcs, no ways out, and a "
    "`board` of two or three offers; " + OFFER_ASK
)
COMMISSION_ASK = (
    "The game master asked for a {kind}: {brief}. Write that one {kind} and nothing else: an "
    "npc stands at the player's place, an item lies at it or on a living npc there, a region "
    "joins the map beyond the player's reach."
)
JOB_BRIEF = (
    "The player is leaving {title} ({place}) on a job. WHAT COMES NEXT is the job they take: an "
    "offer by its title, whose pitch THE BOARD holds, or their own words. Write the "
    "job as a whole new region joining the map at {place}: a complete dungeon by the opening "
    "map's bar, its start known and named after the offer, since the ledger lists the job by that "
    'name. Old dungeons stay on the map, so write only new ids. An offer marked "(left open)" '
    "is a job taken before: name the start of the new region exactly as the offer; it joins the "
    "map at that job's own start, not the tavern, and holds only the part not yet walked."
)


def worldsmith_prompt(
    role: str,
    *,
    source: str,
    map_so_far: str,
    history: str,
    player: str,
    intent: str,
    guidance: str,
    answer: type[BaseModel],
    hub: Sections = (),
    asked: str = "",
) -> str:
    return sections(
        (
            ("YOUR ROLE", role),
            ("SOURCE MATERIAL", source or "(none — write from the setting)"),
            ("MAP SO FAR", map_so_far),
            ("SCENES SO FAR", history),
            *hub,
            ("THE PLAYER", player),
            *((("THE GAME MASTER ASKED FOR", asked),) if asked else ()),
            ("WHAT COMES NEXT", intent),
            ("ENGINE GUIDANCE", guidance),
            ("ANSWER WITH", schema_text(answer)),
        )
    )


def map_refusal[N: Dweller](draft: MapDraft[N]) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    unmet = _map_unmet(draft) + _board_unmet(draft)
    return None if not unmet else "the map needs " + "; ".join(unmet)


def hub_refusal[N: Dweller](draft: MapDraft[N]) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    unmet = _hub_unmet(draft)
    return None if not unmet else "the tavern needs " + "; ".join(unmet)


def job_refusal[N: Dweller](
    draft: MapDraft[N], world: Dungeon[N], asked: Sequence[Commission] = ()
) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    unmet = (
        _map_unmet(draft)
        + _overlap_unmet(draft, world)
        + _board_unmet(draft)
        + _asked_unmet(draft, asked)
    )
    return None if not unmet else "the job's region needs " + "; ".join(unmet)


def extension_refusal[N: Dweller](
    draft: MapDraft[N], world: Dungeon[N], asked: Sequence[Commission] = ()
) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    unmet = (
        _extension_unmet(draft)
        + _overlap_unmet(draft, world)
        + _board_unmet(draft)
        + _asked_unmet(draft, asked)
    )
    return None if not unmet else "the extension needs " + "; ".join(unmet)


def return_refusal[N: Dweller, P: Person](draft: ReturnDraft, world: RoomWorld[N, P]) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    unmet = _recaps_unmet(draft, world) + _debrief_unmet(draft, world)
    return None if not unmet else "the return needs " + "; ".join(unmet)


def npc_refusal[N: Dweller, P: Person](draft: NpcDraft[N], world: RoomWorld[N, P]) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    npc = draft.npc
    unmet: list[str] = []
    if world.entity(npc.id) is not None:
        unmet.append("a new id")
    if npc.place != world.current.id:
        unmet.append(f"the player's place {world.current.id!r}")
    if npc.known:
        unmet.append("unmet")
    if why := npc.unwritten():
        unmet.append(why)
    return None if not unmet else "the npc needs " + "; ".join(unmet)


def item_refusal[N: Dweller, P: Person](draft: ItemDraft, world: RoomWorld[N, P]) -> str | None:
    """Free: the world may not import the drafts; one bar module for map, hub, job and return."""
    item = draft.item
    unmet: list[str] = []
    if world.entity(item.id) is not None:
        unmet.append("a new id")
    holders = {world.current.id, *(npc.id for npc in world.at(world.current.id) if npc.alive)}
    if item.on not in holders:
        unmet.append("lying at the player's place or on a living npc there")
    if item.known:
        unmet.append("unmet")
    return None if not unmet else "the item needs " + "; ".join(unmet)


def _recaps_unmet[N: Dweller, P: Person](draft: ReturnDraft, world: RoomWorld[N, P]) -> list[str]:
    job = world.walked_job()
    if job is None:
        return []
    walked = set(world.walked_places(job))
    given = set(draft.recaps)
    unmet: list[str] = []
    if missing := sorted(walked - given):
        unmet.append(f"a recap for each place walked, missing: {missing}")
    if extra := sorted(given - walked):
        unmet.append(f"recaps only for places walked, not: {extra}")
    return unmet


def _debrief_unmet[N: Dweller, P: Person](draft: ReturnDraft, world: RoomWorld[N, P]) -> list[str]:
    hidden = [
        entity for entity in (*world.npcs.values(), *world.items.values()) if not entity.known
    ]
    found = sorted(named_unmet(draft.debrief, hidden))
    return [f"the debrief silent about unmet npcs and items: {found}"] if found else []


def _map_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
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


def _hub_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
    unmet = _start_unmet(draft)
    if draft.board is None:
        unmet.append("a `board` of two or three offers")
    return unmet


def _start_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
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


def _extension_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
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


def _overlap_unmet[N: Dweller](draft: MapDraft[N], world: Dungeon[N]) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []


def _board_unmet[N: Dweller](draft: MapDraft[N]) -> list[str]:
    if draft.board is not None:
        return ["no `board`: only a campaign's opening tavern carries one"]
    return []


def _has_hidden_thing[N: Dweller](draft: MapDraft[N]) -> bool:
    return any(not entity.known for entity in (*draft.npcs.values(), *draft.items.values()))


def _asked_unmet[N: Dweller](draft: MapDraft[N], asked: Sequence[Commission]) -> list[str]:
    """A `region` commission is met by the write itself; it counts nothing here."""
    unmet: list[str] = []
    for kind, written in (("npc", len(draft.npcs)), ("item", len(draft.items))):
        wanted = sum(1 for commission in asked if commission.kind == kind)
        if written < wanted:
            unmet.append(f"{wanted} {kind}s asked for, {written} written")
    return unmet
