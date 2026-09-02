import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from aidm.core.entities import CheckedEntityId, EngineId, EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import ENCODING
from aidm.core.model import AnyScenario, ScenarioKind, ScenarioMeta, WorldsmithAnswer
from aidm.core.play import Exchange
from aidm.core.tools import schema_of
from aidm.core.views import Rows, sections
from aidm.engines.hub import (
    BOARD_MAX,
    BOARD_MIN,
    OFFER_ASK,
    RETURN_BRIEF,
    Debrief,
    Offer,
    board_lines,
    job_closed,
    ledger,
)
from aidm.engines.tunnelgoons.views import REPORT_IN, entity_line
from aidm.engines.tunnelgoons.world import (
    Dungeon,
    MapCanon,
    Place,
    TunnelGoonsGame,
    TunnelGoonsScenario,
    TunnelGoonsScenarioFile,
    TunnelWorld,
    Way,
    frontier,
    has_shortcut,
    walk,
)

MIN_PLACES = 4
MIN_EXTENSION_PLACES = 2
TAIL_EXCHANGES = 3
WORLDSMITH = (Path(__file__).parent / "worldsmith.md").read_text(encoding=ENCODING)
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

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: CheckedEntityId
    board: tuple[Offer, ...] = ()  # a campaign's opening tavern only


class ReturnDraft(Frozen):
    """The report at the tavern: the paragraph; `finished` is `world.job_done`."""

    debrief: str = Field(min_length=1)
    offers: tuple[Offer, ...] = Field(min_length=BOARD_MIN, max_length=BOARD_MAX)


def opening_draft(_kind: ScenarioKind) -> type[MapDraft]:
    """One map serves both kinds: a campaign's hub is a place on it."""
    return MapDraft


def map_refusal(draft: MapDraft) -> str | None:
    unmet = _map_unmet(draft) + _board_unmet(draft)
    return None if not unmet else "the map needs " + "; ".join(unmet)


def hub_refusal(draft: MapDraft) -> str | None:
    unmet = _hub_unmet(draft)
    return None if not unmet else "the tavern needs " + "; ".join(unmet)


def job_refusal(draft: MapDraft, world: TunnelWorld) -> str | None:
    unmet = _map_unmet(draft) + _overlap_unmet(draft, world) + _board_unmet(draft)
    return None if not unmet else "the job's region needs " + "; ".join(unmet)


def extension_refusal(draft: MapDraft, world: TunnelWorld) -> str | None:
    unmet = _extension_unmet(draft) + _overlap_unmet(draft, world) + _board_unmet(draft)
    return None if not unmet else "the extension needs " + "; ".join(unmet)


def opening_canon(draft: MapDraft, source: str, kind: ScenarioKind) -> MapCanon:
    return MapCanon.model_validate(
        {**draft.model_dump(), "source": source, "hub": draft.start if kind == "campaign" else None}
    )


def attach(world: TunnelWorld, draft: MapDraft, *, known: bool) -> None:
    """No bar runs here: every caller refuses first, so a rejected region leaves the world alone."""
    anchor_id = world.current.id
    world.places.update(draft.places)
    world.ways.update(draft.ways)
    world.npcs.update(draft.npcs)
    world.items.update(draft.items)
    _append_way(world.ways, anchor_id, draft.start, known)
    _append_way(world.ways, draft.start, anchor_id, known)


def install_extension(state: TunnelGoonsGame, written: BaseModel) -> tuple[Fact, ...]:
    world = state.payload.world
    if isinstance(written, ReturnDraft):
        world.visit.debrief = Debrief(text=written.debrief, finished=world.job_done)
        world.visit.job = ""
        world.job_done = False
        world.board = written.offers
        return (job_closed(world.jobs()[-1]),)
    if isinstance(written, MapDraft) and world.at_hub:
        if (refused := job_refusal(written, world)) is not None:
            raise ValueError(refused)
        tavern = world.current
        attach(world, written, known=True)
        start = written.places[written.start]
        world.visit.job = start.name
        trace = f"a way opens from {tavern.name} to {start.name}"
        card = f"A way opens: {start.name}"
        return (Fact(kind="job_taken", told=True, trace=trace, card=card),)
    if isinstance(written, MapDraft):
        if (refused := extension_refusal(written, world)) is not None:
            raise ValueError(refused)
        anchor = world.current.name
        attach(world, written, known=False)
        trace = f"a hidden region opens beyond {anchor}"
        return (Fact(kind="region_added", trace=trace, told=False),)
    raise ValueError("Tunnel Goons received an incompatible map")


async def write_extension(
    state: TunnelGoonsGame, intent: str, answer: WorldsmithAnswer
) -> BaseModel:
    world = state.payload.world
    if world.at_hub and intent == REPORT_IN:
        if not world.job_open:
            raise ValueError("no job is open to report")
        return await answer(_render_return(world), ReturnDraft, lambda _written: None)
    if world.at_hub and world.job_open:
        raise ValueError("report the open job first")

    bar = job_refusal if world.at_hub else extension_refusal
    prompt = _render_job(world, intent) if world.at_hub else _render_extension(world, intent)

    def refusal(written: BaseModel) -> str | None:
        if not isinstance(written, MapDraft):
            raise ValueError("Tunnel Goons received an incompatible map")
        return bar(written, world)

    return await answer(prompt, MapDraft, refusal)


def render_map(source: str, picks: Sequence[Slug], kind: ScenarioKind) -> str:
    """`Authoring.prompt`; `picks` stays unused — Tunnel Goons ships no packs to pick from."""
    map_so_far = TAVERN_ASK if kind == "campaign" else "(no map yet — write the opening map)"
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none — write from the setting)"),
            ("MAP SO FAR", map_so_far),
            ("ANSWER WITH", json.dumps(schema_of(MapDraft), indent=2, ensure_ascii=False)),
        )
    )


def build_scenario(
    title: str,
    premise: str,
    packs: tuple[Slug, ...],
    written: BaseModel,
    source: str,
    kind: ScenarioKind,
) -> AnyScenario:
    if not isinstance(written, MapDraft):
        raise ValueError("Tunnel Goons received an incompatible map")
    bar = hub_refusal if kind == "campaign" else map_refusal
    if (refused := bar(written)) is not None:
        raise ValueError(refused)
    return TunnelGoonsScenarioFile(
        meta=ScenarioMeta(
            title=title, premise=premise or written.places[written.start].description, kind=kind
        ),
        engine=EngineId("tunnelgoons"),
        packs=packs,
        payload=TunnelGoonsScenario(world=opening_canon(written, source, kind)),
    )


def way_open(state: TunnelGoonsGame) -> bool:
    world = state.payload.world
    return world.at_hub or frontier(world) == 0


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
    if not has_shortcut(draft.ways):
        unmet.append("a shortcut with an alternate route")
    return unmet


def _hub_unmet(draft: MapDraft) -> list[str]:
    unmet = _start_unmet(draft)
    if not BOARD_MIN <= len(draft.board) <= BOARD_MAX:
        unmet.append(f"a `board` of two or three offers; it has {len(draft.board)}")
    return unmet


def _start_unmet(draft: MapDraft) -> list[str]:
    places = draft.places
    unmet: list[str] = []
    if draft.start not in places:
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if not places[draft.start].known:
            unmet.append("the starting place known to the player")
        if missing := sorted(set(places) - walk(draft.ways, draft.start)):
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
        if missing := sorted(set(places) - walk(draft.ways, draft.start)):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    if not any(way for leaving in draft.ways.values() for way in leaving):
        unmet.append("ways connecting the new places")
    if not _has_hidden_thing(draft):
        unmet.append("at least one hidden npc or item")
    return unmet


def _overlap_unmet(draft: MapDraft, world: TunnelWorld) -> list[str]:
    existing = {*world.places, *world.npcs, *world.items}
    added = {*draft.places, *draft.npcs, *draft.items}
    if overlap := sorted(existing & added):
        return [f"ids not already in the world: {overlap}"]
    return []


def _board_unmet(draft: MapDraft) -> list[str]:
    if draft.board:
        return ["no `board`: only a campaign's opening tavern carries one"]
    return []


def _has_hidden_thing(draft: MapDraft) -> bool:
    return any(not one.known for one in (*draft.npcs.values(), *draft.items.values()))


def _append_way(
    ways: dict[EntityId, tuple[Way, ...]], from_id: EntityId, to_id: EntityId, known: bool
) -> None:
    ways[from_id] = (*ways.get(from_id, ()), Way(to=to_id, known=known))


def _render_extension(world: TunnelWorld, intent: str, hub: Rows = ()) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", world.source or "(none — write from the setting)"),
            ("MAP SO FAR", _map_so_far(world)),
            *hub,
            ("THE PLAYER", entity_line(world, world.player)),
            ("WHAT THE PLAYER WANTS TO PURSUE", intent),
            ("ANSWER WITH", json.dumps(schema_of(MapDraft), indent=2, ensure_ascii=False)),
        )
    )


def _render_job(world: TunnelWorld, intent: str) -> str:
    return _render_extension(
        world,
        intent,
        (
            ("JOBS SO FAR", ledger(world.jobs())),
            ("THE BOARD", board_lines(world.board)),
            ("THE HUB", JOB_BRIEF.format(title=world.current.name, place=world.hub)),
        ),
    )


def _told_tail(exchanges: Sequence[Exchange]) -> str:
    return "\n".join(f"> {one.prompt}\n{one.narration}" for one in exchanges[-TAIL_EXCHANGES:])


def _render_return(world: TunnelWorld) -> str:
    this_job = "\n\n".join(
        f"{world.require_place(visit.place).name}[{visit.place}]\n"
        + (_told_tail(visit.exchanges) or "(nothing said)")
        for visit in world.job_visits()
    )
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", world.source or "(none — write from the setting)"),
            ("MAP SO FAR", _map_so_far(world)),
            ("JOBS SO FAR", ledger(world.jobs())),
            ("THIS JOB", this_job),
            ("THE BOARD", board_lines(world.board)),
            ("THE VERDICT", "finished" if world.job_done else "left open"),
            ("THE PLAYER", entity_line(world, world.player)),
            ("WHAT COMES NEXT", RETURN_BRIEF.format(title=world.current.name, place=world.hub)),
            ("ANSWER WITH", json.dumps(schema_of(ReturnDraft), indent=2, ensure_ascii=False)),
        )
    )


def _map_so_far(world: TunnelWorld) -> str:
    seen: dict[EntityId, Place] = {}
    for visit in world.visits:
        seen.setdefault(visit.place, world.require_place(visit.place))
    lines: list[str] = []
    for place in seen.values():
        known_ways = ", ".join(
            world.require_place(one.to).name for one in world.ways.get(place.id, ()) if one.known
        )
        lines.append(
            f"{place.name}[{place.id}] — {place.description}\n"
            f"  known ways out: {known_ways or '(none)'}"
        )
    return "\n".join(lines)
