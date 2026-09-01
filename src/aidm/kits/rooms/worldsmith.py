import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field, model_validator

from aidm.core.entities import CheckedEntityId, EntityId, Frozen, Slug
from aidm.core.facts import Fact
from aidm.core.io import engine_text
from aidm.core.model import WorldsmithAnswer
from aidm.core.tools import schema_of
from aidm.core.views import sections
from aidm.kits.entities import Entity, Thread
from aidm.kits.rooms.render import entity_line, thread_lines
from aidm.kits.rooms.state import RoomCanon, RoomWorld, Way

MIN_PLACES = 4
MIN_EXTENSION_PLACES = 2
WORLDSMITH = engine_text(Path(__file__).parent / "worldsmith.md")


class MapDraft[S: BaseModel](Frozen):
    """The worldsmith's complete authored map, before the engine adds its player."""

    cast: dict[EntityId, Entity[S]] = Field(default_factory=dict)
    ways: dict[EntityId, tuple[Way, ...]] = Field(default_factory=dict)
    start: CheckedEntityId
    threads: dict[Slug, Thread] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> "MapDraft[S]":
        RoomCanon[S](
            cast=self.cast,
            ways=self.ways,
            start=self.start,
            threads=self.threads,
        )
        return self


def opening_canon[S: BaseModel](draft: MapDraft[S], source: str) -> RoomCanon[S]:
    return RoomCanon[S](
        cast=deepcopy(draft.cast),
        ways=deepcopy(draft.ways),
        start=draft.start,
        threads=deepcopy(draft.threads),
        source=source,
    )


def map_refusal[S: BaseModel](draft: MapDraft[S]) -> str | None:
    unmet = _map_unmet(draft)
    return None if not unmet else "the map needs " + "; ".join(unmet)


def extension_refusal[S: BaseModel](
    draft: MapDraft[S], world: RoomWorld[S] | None = None
) -> str | None:
    """The region bar runs before install; the whole-world bar runs in `apply_extension`."""
    unmet = _extension_unmet(draft, world)
    return None if not unmet else "the extension needs " + "; ".join(unmet)


def apply_extension[S: BaseModel](world: RoomWorld[S], draft: MapDraft[S]) -> None:
    """Join a hidden authored region atomically, then validate the complete graph."""
    if refused := extension_refusal(draft, world):
        raise ValueError(refused)
    anchor_id = world.current.id
    anchor = world.require_kind(anchor_id, "place")
    if not anchor.known:
        raise ValueError(f"the extension must join a known place, not {anchor_id!r}")

    candidate = world.model_copy(deep=True)
    added = deepcopy(draft.cast)
    for entity in added.values():
        entity.known = False
    candidate.cast.update(added)
    candidate.ways.update(deepcopy(draft.ways))
    candidate.threads.update(deepcopy(draft.threads))
    _append_way(candidate.ways, anchor_id, draft.start)
    _append_way(candidate.ways, draft.start, anchor_id)
    type(world).model_validate(candidate)
    _require_world_reachability(candidate)

    world.cast = candidate.cast
    world.ways = candidate.ways
    world.threads = candidate.threads


def install_extension[S: BaseModel](world: RoomWorld[S], draft: MapDraft[S]) -> tuple[Fact, ...]:
    apply_extension(world, draft)
    return (
        Fact(
            kind="region_materialized",
            trace=f"materialized an authored region at {world.require(draft.start).name}",
            told=False,
        ),
    )


async def write_extension[S: BaseModel](
    world: RoomWorld[S],
    draft_type: type[MapDraft[S]],
    intent: str,
    guidance: str,
    rows: Callable[[EntityId], tuple[tuple[str, str], ...]],
    answer: WorldsmithAnswer,
) -> MapDraft[S]:
    """Ask the worldsmith for a typed region and retry once through the role boundary."""

    def refusal(written: BaseModel) -> str | None:
        return extension_refusal(cast(MapDraft[S], written), world)

    written = await answer(
        render_extension(world, intent, guidance, draft_type, rows), draft_type, refusal
    )
    return cast(MapDraft[S], written)


def render_map(source: str, guidance: str, answer: type[BaseModel]) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", source or "(none)"),
            ("MAP SO FAR", "(no map yet — write the opening map)"),
            ("THE WHOLE CAST", "(no cast yet)"),
            ("THREADS", "- (none yet)"),
            ("ENGINE GUIDANCE", guidance),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def render_extension[S: BaseModel](
    world: RoomWorld[S],
    intent: str,
    guidance: str,
    answer: type[BaseModel],
    rows: Callable[[EntityId], tuple[tuple[str, str], ...]],
) -> str:
    return sections(
        (
            ("YOUR ROLE", WORLDSMITH),
            ("SOURCE MATERIAL", world.source or "(none)"),
            ("MAP SO FAR", "\n".join(f"VISIT {one.place}" for one in world.visits)),
            (
                "THE WHOLE CAST",
                "\n".join(entity_line(world, one, rows) for one in world.cast.values()) or "(none)",
            ),
            ("THREADS", thread_lines(world.threads.values(), standing_only=True)),
            ("ENGINE GUIDANCE", guidance),
            ("WHAT THE PLAYER WANTS TO PURSUE", intent),
            ("ANSWER WITH", json.dumps(schema_of(answer), indent=2, ensure_ascii=False)),
        )
    )


def _map_unmet[S: BaseModel](draft: MapDraft[S]) -> list[str]:
    cast = draft.cast
    places = [one.id for one in cast.values() if one.kind == "place"]
    unmet: list[str] = []
    if len(places) < MIN_PLACES:
        unmet.append(f"four or more places; the map has {len(places)}: {sorted(places)}")
    if draft.start not in cast or cast[draft.start].kind != "place":
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if not cast[draft.start].known:
            unmet.append("the starting place known to the player")
        reached = walk(draft.cast, draft.ways, draft.start)
        if missing := sorted(set(places) - reached):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
        if not any(way.known for way in draft.ways.get(draft.start, ())):
            unmet.append("at least one starting way known to the player")
    ways = [way for leaving in draft.ways.values() for way in leaving]
    if not any(not way.known for way in ways):
        unmet.append("at least one way starting unknown")
    if not any(way.locked for way in ways):
        unmet.append("at least one way starting locked")
    if not any(not one.known for one in cast.values() if one.kind != "place"):
        unmet.append("at least one hidden actor, item, or prop")
    if not _has_shortcut(draft.cast, draft.ways):
        unmet.append("a shortcut with an alternate route")
    if not draft.threads:
        unmet.append("at least one thread")
    return unmet


def _extension_unmet[S: BaseModel](draft: MapDraft[S], world: RoomWorld[S] | None) -> list[str]:
    places = [one.id for one in draft.cast.values() if one.kind == "place"]
    unmet: list[str] = []
    if len(places) < MIN_EXTENSION_PLACES:
        unmet.append(f"two or more new places; the region has {len(places)}: {sorted(places)}")
    if draft.start not in draft.cast or draft.cast[draft.start].kind != "place":
        unmet.append(f"a starting place {draft.start!r}")
    else:
        if draft.cast[draft.start].known:
            unmet.append("a starting place hidden from the player")
        reached = walk(draft.cast, draft.ways, draft.start)
        if missing := sorted(set(places) - reached):
            unmet.append(f"places no walk of ways reaches from {draft.start!r}: {missing}")
    ways = [way for leaving in draft.ways.values() for way in leaving]
    if not ways:
        unmet.append("ways connecting the new places")
    if not any(not one.known for one in draft.cast.values() if one.kind != "place"):
        unmet.append("at least one hidden actor, item, or prop")
    if world is not None:
        if not world.current.known:
            unmet.append("a known place to join")
        if overlap := sorted(set(world.cast) & set(draft.cast)):
            unmet.append(f"ids not already in the world: {overlap}")
        if overlap_threads := sorted(set(world.threads) & set(draft.threads)):
            unmet.append(f"thread ids not already in the world: {overlap_threads}")
    return unmet


def _append_way(ways: dict[EntityId, tuple[Way, ...]], from_id: EntityId, to_id: EntityId) -> None:
    if any(one.to == to_id for one in ways.get(from_id, ())):
        raise ValueError(f"a way already leads from {from_id!r} to {to_id!r}")
    ways[from_id] = (*ways.get(from_id, ()), Way(to=to_id))


def _require_world_reachability[S: BaseModel](world: RoomWorld[S]) -> None:
    start = world.visits[0].place
    places = {one.id for one in world.cast.values() if one.kind == "place"}
    if missing := sorted(places - walk(world.cast, world.ways, start)):
        raise ValueError(f"places no walk of ways reaches from {start!r}: {missing}")


def walk[S: BaseModel](
    cast: dict[EntityId, Entity[S]], ways: dict[EntityId, tuple[Way, ...]], start: EntityId
) -> set[EntityId]:
    reached = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for way in ways.get(current, ()):
            if way.to not in reached and way.to in cast:
                reached.add(way.to)
                pending.append(way.to)
    return reached


def _has_shortcut[S: BaseModel](
    cast: dict[EntityId, Entity[S]], ways: dict[EntityId, tuple[Way, ...]]
) -> bool:
    """A shortcut is an edge whose destination remains reachable after that edge is removed."""
    for start, leaving in ways.items():
        for direct in leaving:
            pending = [start]
            reached = {start}
            while pending:
                current = pending.pop()
                for way in ways.get(current, ()):
                    if current == start and way.to == direct.to:
                        continue
                    if way.to not in reached and way.to in cast:
                        reached.add(way.to)
                        pending.append(way.to)
            if direct.to in reached:
                return True
    return False
