from collections.abc import Sequence
from typing import Any

from aidm.core.model import Game
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView, Subject, speaker_of
from aidm.engines.core import Person, party_panel
from aidm.engines.hub import board_panel, jobs_panel
from aidm.engines.scenes.world import SceneRun, SceneState, player_over


def trail_panel(runs: Sequence[SceneRun]) -> Panel:
    return Panel(
        title="Trail", rows=tuple(PanelRow(label=one.scene.title, detail="") for one in runs)
    )


def narrator_view[S: SceneState[Any, Any]](state: Game[S]) -> NarratorView:
    world = state.payload.world
    scene = world.current
    here = [one for one in world.here() if one.known]
    return NarratorView(
        place=scene.place,
        title=scene.title,
        focus=scene.question,
        situation=scene.situation,
        art_prompt="\n".join(
            (
                f"The place: {scene.title} — {scene.situation}",
                *(f"Present: {one.name} — {one.brief}" for one in here),
            )
        ),
        subjects=tuple(_subject_of(one) for one in here),
        speakers=tuple(speaker_of(_subject_of(one)) for one in here),
    )


def player_view[S: SceneState[Any, Any]](state: Game[S], extra: tuple[Panel, ...]) -> PlayerView:
    world = state.payload.world
    player = world.player
    here_rows = (
        PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id),
        *(
            PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
            for one in world.here()
            if one.known and one.id != player.id
        ),
    )
    return PlayerView(
        player=_subject_of(player),
        panels=(
            Panel(
                title="Character",
                rows=tuple(PanelRow(label=label, detail=detail) for label, detail in player.rows()),
            ),
            *extra,
            Panel(title="This scene", rows=world.scene_rows()),
            *board_panel(world.at_hub, world.board),
            *party_panel(world.members()),
            Panel(title="Here", rows=here_rows),
            trail_panel(world.job_runs()),
            *jobs_panel(world.jobs()),
        ),
        prompt=state.pending,
        over=player_over(state),
    )


def _subject_of(one: Person) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)
