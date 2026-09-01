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
from aidm.engines.breathless.world import (
    BreathlessGame,
    Npc,
    Survivor,
    player_over,
)


def subject_of(one: Survivor | Npc) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def entity_line(one: Survivor | Npc, *, detail: str = "") -> str:
    line = f"- {one.name}[{one.id}] — {one.brief}"
    if not one.alive:
        line += " (dead)"
    parts = [line]
    if isinstance(one, Survivor):
        if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in one.rows()):
            parts.append(f"  {sheet}")
    if detail:
        parts.append(f"  {detail}")
    return "\n".join(parts)


def entity_lines(entities: Iterable[Survivor | Npc]) -> str:
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
    scene_rows = [PanelRow(label=world.current.question, detail="")]
    if world.run.settled:
        scene_rows.append(
            PanelRow(label="Way on", detail="Keep playing, or name where you go and move on.")
        )
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
            Panel(title="This scene", rows=tuple(scene_rows)),
            Panel(title="Here", rows=tuple(here_rows)),
            Panel(
                title="Trail",
                rows=tuple(PanelRow(label=one.scene.title, detail="") for one in world.runs),
            ),
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
        ("THE QUESTION THIS SCENE SETTLES", scene.question),
        ("YOU PLAY FOR", entity_line(player)),
        ("BACKPACK", "\n".join(backpack_lines) or "- (none)"),
        (
            "HERE WITH THE PLAYER",
            entity_lines(one for one in world.here() if one.id != player.id),
        ),
        (
            "HIDDEN HERE (the player has not found these)",
            entity_lines(world.require(one) for one in world.run.hidden),
        ),
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
    )


def _entity_row(one: Survivor | Npc) -> PanelRow:
    return PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
