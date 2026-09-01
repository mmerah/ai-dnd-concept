from typing import Any

from pydantic import BaseModel

from aidm.core.model import AnyGame, Game
from aidm.core.views import NarratorView, PlayerView, Rows, ThreadRow, speaker_of
from aidm.kits.entities import Entity
from aidm.kits.render import (
    EngineSections,
    SheetRows,
    entity_lines,
    player_prompt,
    subject_of,
    thread_lines,
)
from aidm.kits.render import (
    entity_line as line_of,
)
from aidm.kits.scenes.state import SceneState


def entity_line[S: BaseModel](
    world: SceneState[S], one: Entity[S], rows: SheetRows, *, where: bool = False
) -> str:
    seen = world.last_seen(one.id) if where else ""
    return line_of(world, one, rows, detail=f"last seen in: {seen}" if seen else "")


def narrator_view[S: BaseModel](world: SceneState[S]) -> NarratorView:
    scene = world.current
    here = [one for one in world.here() if one.known]
    cast = [one for one in here if one.kind == "actor"]
    return NarratorView(
        place=scene.place,
        title=scene.title,
        focus=scene.question,
        situation=scene.situation,
        art_prompt="\n".join(
            (
                f"The place: {scene.title} — {scene.situation}",
                *(f"Present: {one.name} — {one.brief}" for one in cast),
            )
        ),
        subjects=tuple(subject_of(one) for one in cast),
        speakers=tuple(speaker_of(subject_of(one)) for one in cast),
    )


def player_view[S: BaseModel](
    state: AnyGame, world: SceneState[S], rows: SheetRows, over: str | None
) -> PlayerView:
    player = world.player
    return PlayerView(
        player=subject_of(player),
        focus=world.current.question,
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
        trail=tuple(one.scene.title for one in world.runs),
        world_rows=(
            (("Way on", "Keep playing, or name where you go and move on."),)
            if world.run.settled
            else ()
        ),
        prompt=player_prompt(state),
        over=over,
    )


def master_sections[G: Game[Any], S: BaseModel](
    state: G,
    world: SceneState[S],
    rows: SheetRows,
    engine_sections: EngineSections[G],
) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    scene = world.current
    player = world.player
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        ("THE QUESTION THIS SCENE SETTLES", scene.question),
        ("YOU PLAY FOR", entity_line(world, player, rows)),
        ("CARRYING", entity_lines(world, world.carried_by(player.id), rows)),
        (
            "HERE WITH THE PLAYER",
            entity_lines(world, (one for one in world.here() if one.id != player.id), rows),
        ),
        (
            "HIDDEN HERE (the player has not found these)",
            entity_lines(world, (world.require(one) for one in world.run.hidden), rows),
        ),
        ("ACTIVE THREADS", thread_lines(world.threads.values(), standing_only=True)),
        *engine_sections(state),
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
    )
