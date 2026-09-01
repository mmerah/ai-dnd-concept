from typing import Any

from pydantic import BaseModel

from aidm.core.model import AnyGame, Game
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView, Rows, speaker_of
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
    scene_rows = [PanelRow(label=world.current.question, detail="")]
    if world.run.settled:
        scene_rows.append(
            PanelRow(label="Way on", detail="Keep playing, or name where you go and move on.")
        )
    here_rows = [
        PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id),
        *(_entity_row(one) for one in world.here() if one.known and one.id != player.id),
    ]
    if world.companions:
        here_rows.append(
            PanelRow(
                label="Travelling with",
                detail=", ".join(world.require(one).name for one in world.companions),
            )
        )
    return PlayerView(
        player=subject_of(player),
        sheet=rows(player.id),
        panels=(
            Panel(title="This scene", rows=tuple(scene_rows)),
            Panel(title="Here", rows=tuple(here_rows)),
            Panel(
                title="Traits",
                rows=tuple(PanelRow(label=one.name, detail=one.text) for one in player.traits),
            ),
            Panel(
                title="Carrying",
                rows=tuple(_entity_row(one) for one in world.carried_by(player.id) if one.known),
            ),
            Panel(
                title="Threads",
                rows=tuple(
                    PanelRow(
                        label=(
                            one.title if one.status == "active" else f"{one.title} — {one.status}"
                        ),
                        detail=one.note,
                    )
                    for one in world.threads.values()
                    if one.status != "resolved"
                ),
            ),
            Panel(
                title="Trail",
                rows=tuple(PanelRow(label=one.scene.title, detail="") for one in world.runs),
            ),
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


def _entity_row[S: BaseModel](one: Entity[S]) -> PanelRow:
    return PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
