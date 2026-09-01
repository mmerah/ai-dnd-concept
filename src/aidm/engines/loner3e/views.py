from collections.abc import Iterable, Mapping

from aidm.core.views import (
    NarratorView,
    Panel,
    PanelRow,
    PlayerView,
    Rows,
    Subject,
    player_prompt,
    speaker_of,
)
from aidm.engines.loner3e.creation import Pack
from aidm.engines.loner3e.tools import advance_notes, meanings
from aidm.engines.loner3e.world import Loner3eGame, LonerCharacter, LonerWorld, player_over


def subject_of(one: LonerCharacter) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def entity_line(world: LonerWorld, one: LonerCharacter, *, detail: str = "") -> str:
    parts = [f"- {one.name}[{one.id}] — {one.brief}"]
    if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in one.rows()):
        parts.append(f"  {sheet}")
    if one.id in world.companions:
        parts.append("  travels with the player")
    if detail:
        parts.append(f"  {detail}")
    return "\n".join(parts)


def entity_lines(world: LonerWorld, entities: Iterable[LonerCharacter]) -> str:
    return "\n".join(entity_line(world, one) for one in entities) or "- (none)"


def narrator_view(state: Loner3eGame) -> NarratorView:
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


def player_view(state: Loner3eGame) -> PlayerView:
    world = state.payload.world
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
        panels=(
            Panel(
                title="Character",
                rows=tuple(PanelRow(label=label, detail=detail) for label, detail in player.rows()),
            ),
            Panel(title="This scene", rows=tuple(scene_rows)),
            Panel(title="Here", rows=tuple(here_rows)),
            Panel(
                title="Trail",
                rows=tuple(PanelRow(label=one.scene.title, detail="") for one in world.runs),
            ),
        ),
        prompt=player_prompt(state),
        over=player_over(state),
    )


def master_sections(packs: Mapping[str, Pack], state: Loner3eGame) -> Rows:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.payload.world
    scene = world.current
    player = world.player
    glossary: dict[str, str] = {}
    for one in world.here():
        glossary.update(meanings(packs, state.packs, one))
    lines = "\n".join(f"- {tag}: {detail}" for tag, detail in glossary.items())
    spelled = (("WHAT THE TAGS IN PLAY MEAN", lines),) if glossary else ()
    return (
        ("SCENE", f"{scene.title}\n{scene.situation}"),
        ("THE QUESTION THIS SCENE SETTLES", scene.question),
        ("YOU PLAY FOR", entity_line(world, player)),
        (
            "HERE WITH THE PLAYER",
            entity_lines(world, (one for one in world.here() if one.id != player.id)),
        ),
        (
            "HIDDEN HERE (the player has not found these)",
            entity_lines(world, (world.require(one) for one in world.run.hidden)),
        ),
        *spelled,
        *advance_notes(state),
        ("THE SCENE'S SECRET (never narrate this)", scene.secret or "(none)"),
    )


def _entity_row(one: LonerCharacter) -> PanelRow:
    return PanelRow(label=one.name, detail=one.brief, icon_id=one.id)
