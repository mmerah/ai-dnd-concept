from typing import Any

from pydantic import BaseModel

from aidm.core.model import AnyGame, Game
from aidm.core.views import NarratorView, PlayerView, Rows, ThreadRow, speaker_of
from aidm.kits.render import (
    EngineSections,
    SheetRows,
    entity_line,
    entity_lines,
    player_prompt,
    subject_of,
    thread_lines,
)
from aidm.kits.rooms.state import RoomWorld


def narrator_view[S: BaseModel](world: RoomWorld[S]) -> NarratorView:
    place = world.current
    situation = place.description or place.brief
    actors = [one for one in world.here() if one.kind == "actor" and one.known]
    return NarratorView(
        place=str(place.id),
        title=place.name,
        focus=place.brief,
        situation=situation,
        art_prompt="\n".join(
            (
                f"The place: {place.name} — {situation}",
                *(f"Present: {one.name} — {one.brief}" for one in actors),
            )
        ),
        subjects=tuple(subject_of(one) for one in actors),
        speakers=tuple(speaker_of(subject_of(one)) for one in actors),
    )


def player_view[S: BaseModel](
    state: AnyGame, world: RoomWorld[S], rows: SheetRows, over: str | None
) -> PlayerView:
    player = world.player
    return PlayerView(
        player=subject_of(player),
        focus=world.current.brief,
        sheet=rows(player.id),
        traits=tuple((one.name, one.text) for one in player.traits),
        carrying=tuple(subject_of(one) for one in world.carried_by(player.id) if one.known),
        present=tuple(subject_of(one) for one in world.here() if one.known and one.id != player.id),
        companions=tuple(world.require(one).name for one in world.companions),
        threads=tuple(
            ThreadRow(title=one.title, status=one.status, note=one.note)
            for one in world.threads.values()
            if one.status != "resolved"
        ),
        trail=tuple(world.require(one.place).name for one in world.visits),
        world_rows=way_rows(world),
        prompt=player_prompt(state),
        over=over,
    )


def master_sections[G: Game[Any], S: BaseModel](
    state: G,
    world: RoomWorld[S],
    rows: SheetRows,
    engine_sections: EngineSections[G],
) -> Rows:
    place = world.current
    here = list(world.here())
    return (
        ("CURRENT PLACE", f"{place.name}[{place.id}]\n{place.description or place.brief}"),
        ("YOU PLAY FOR", entity_line(world, world.player, rows)),
        ("CARRYING", entity_lines(world, world.carried_by(world.player_id), rows)),
        (
            "HERE WITH THE PLAYER",
            entity_lines(world, (one for one in here if one.id != world.player_id), rows),
        ),
        (
            "HIDDEN HERE (the player has not found these)",
            entity_lines(world, (one for one in here if not one.known), rows),
        ),
        ("WAYS OUT", way_lines(world)),
        ("ACTIVE THREADS", thread_lines(world.threads.values(), standing_only=True)),
        *engine_sections(state),
    )


def way_rows[S: BaseModel](world: RoomWorld[S]) -> Rows:
    return tuple(
        (
            world.require(way.to).name,
            " → " + str(way.to) + (" (locked)" if way.locked else ""),
        )
        for way in world.ways.get(world.current.id, ())
        if way.known
    )


def way_lines[S: BaseModel](world: RoomWorld[S]) -> str:
    return (
        "\n".join(
            f"- {world.require(way.to).name}[{way.to}] — "
            f"{'known' if way.known else 'unknown'}"
            f"{'; locked' if way.locked else ''}"
            for way in world.ways.get(world.current.id, ())
        )
        or "- (none)"
    )
