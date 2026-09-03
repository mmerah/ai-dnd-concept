from typing import Any

from aidm.core.model import Game
from aidm.core.views import NarratorView, Panel, PlayerView, Subject, speaker_of
from aidm.engines.base import Person, character_panel, here_panel, party_panel, trail_panel
from aidm.engines.hub import board_panel, jobs_panel
from aidm.engines.scenes.world import SceneWorld, player_over


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
    me = _subject_of(player)
    return PlayerView(
        player=me,
        panels=(
            character_panel(player.rows()),
            *extra,
            Panel(title="This scene", rows=world.scene_rows()),
            *board_panel(world.at_hub, world.board),
            *party_panel(world.members()),
            here_panel(
                me,
                (_subject_of(one) for one in world.here() if one.id != player.id),
            ),
            trail_panel(run.title for run in world.job_runs()),
            *jobs_panel(world.closed_jobs()),
        ),
        prompt=state.pending,
        over=player_over(state),
    )


def _subject_of(one: Person) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)
