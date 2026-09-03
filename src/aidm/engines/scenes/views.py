from collections.abc import Sequence
from typing import Any

from aidm.core.model import Game
from aidm.core.views import NarratorView, Panel, PanelRow, PlayerView, Subject, speaker_of
from aidm.engines.core import Person, party_panel
from aidm.engines.hub import board_panel, jobs_panel
from aidm.engines.scenes.world import SceneRun, SceneWorld, player_over


def trail_panel(runs: Sequence[SceneRun]) -> Panel:
    return Panel(title="Trail", rows=tuple(PanelRow(label=one.title, detail="") for one in runs))


def narrator_view[W: SceneWorld[Any, Any]](state: Game[W]) -> NarratorView:
    world = state.payload
    scene = world.run
    here = list(world.here())
    return NarratorView(
        place=scene.place,
        title=scene.title,
        focus=scene.question,
        situation=scene.situation,
        subjects=tuple(_subject_of(one) for one in here),
        speakers=tuple(speaker_of(_subject_of(one)) for one in here),
    )


def player_view[W: SceneWorld[Any, Any]](state: Game[W], extra: tuple[Panel, ...]) -> PlayerView:
    world = state.payload
    player = world.player
    here_rows = (
        PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id),
        *(
            PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
            for one in world.here()
            if one.id != player.id
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
            *jobs_panel(world.closed_jobs()),
        ),
        prompt=state.pending,
        over=player_over(state),
    )


def _subject_of(one: Person) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)
