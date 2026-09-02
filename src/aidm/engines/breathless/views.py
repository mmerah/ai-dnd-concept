from collections.abc import Iterable

from aidm.core.views import (
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Rows,
    Subject,
    speaker_of,
)
from aidm.engines.breathless.world import BreathlessGame
from aidm.engines.core import Person
from aidm.engines.hub import board_panel, jobs_panel, master_tail, question_heading
from aidm.engines.scenes import player_over, scene_rows, trail_panel


def subject_of(one: Person) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def entity_line(one: Person, *, detail: str = "") -> str:
    line = f"- {one.name}[{one.id}] — {one.brief}"
    if not one.alive:
        line += " (dead)"
    parts = [line]
    if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in one.rows()):
        parts.append(f"  {sheet}")
    if detail:
        parts.append(f"  {detail}")
    return "\n".join(parts)


def entity_lines(entities: Iterable[Person]) -> str:
    return "\n".join(entity_line(one) for one in entities) or "- (none)"


def narrator_view(state: BreathlessGame) -> NarratorView:
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
        subjects=tuple(subject_of(one) for one in here),
        speakers=tuple(speaker_of(subject_of(one)) for one in here),
    )


def player_view(state: BreathlessGame) -> PlayerView:
    world = state.payload.world
    player = world.player
    backpack_rows = [
        PanelRow(label=item.name, detail=f"d{item.die}") for item in player.items.values()
    ]
    if player.med_kit:
        backpack_rows.append(PanelRow(label="Med kit", detail="held"))
    here_rows = [
        PanelRow(label=f"{player.name} (you)", detail=player.brief, icon_id=player.id),
        *(_entity_row(one) for one in world.here() if one.known and one.id != player.id),
    ]
    return PlayerView(
        player=subject_of(player),
        panels=(
            Panel(
                title="Character",
                rows=tuple(PanelRow(label=label, detail=detail) for label, detail in player.rows()),
            ),
            Panel(title="Backpack", rows=tuple(backpack_rows)),
            Panel(title="This scene", rows=scene_rows(world)),
            *board_panel(world.at_hub, world.board),
            Panel(title="Here", rows=tuple(here_rows)),
            trail_panel(world.job_runs()),
            *jobs_panel(world.jobs()),
        ),
        prompt=state.pending,
        over=player_over(state),
    )


def master_sections(state: BreathlessGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload.world
    scene = world.current
    player = world.player
    backpack_lines = [f"- {item.name}[{key}] — d{item.die}" for key, item in player.items.items()]
    if player.med_kit:
        backpack_lines.append("- med kit")
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        (question_heading(world.at_hub), scene.question),
        ("YOU PLAY FOR", entity_line(player)),
        ("BACKPACK", "\n".join(backpack_lines) or "- (none)"),
        ("HERE WITH THE PLAYER", entity_lines(one for one in world.here() if one.id != player.id)),
        (
            "HIDDEN HERE (the player has not found these)",
            entity_lines(world.require(one) for one in world.run.hidden),
        ),
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
        *master_tail(world.hub, world.at_hub, world.board, world.jobs(), world.job),
    )


def _entity_row(one: Person) -> PanelRow:
    return PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
