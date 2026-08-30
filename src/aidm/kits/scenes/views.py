from collections.abc import Callable, Iterable

from pydantic import BaseModel

from aidm.kernel.views import (
    DirectorView,
    NarratorView,
    PlayerPrompt,
    PlayerView,
    Subject,
    speaker_of,
)
from aidm.kits.scenes.state import Entity, SceneState, Thread
from aidm.state.entities import EntityId
from aidm.state.model import Game
from aidm.state.play import DecisionOption

# The engine's own sheet rows for one entity; empty for scenery nothing rolls against.
type SheetRows = Callable[[EntityId], tuple[tuple[str, str], ...]]
# Sections only the engine can state, such as the advances it owes the party.
type EngineSections = Callable[[Game], tuple[tuple[str, str], ...]]


def entity_line[S: BaseModel](
    world: SceneState[S], one: Entity[S], rows: SheetRows, *, where: bool = False
) -> str:
    parts = [f"- {one.name}[{one.id}] ({one.kind}) — {one.brief}"]
    if one.description:
        parts.append(f"  detail: {one.description}")
    if sheet := "; ".join(f"{label.lower()}: {value}" for label, value in rows(one.id) if value):
        parts.append(f"  {sheet}")
    if one.traits:
        parts.append("  traits: " + ", ".join(f"{t.name}[{t.id}]" for t in one.traits))
    if one.carried_by is not None:
        parts.append(f"  carried by {world.label(world.require(one.carried_by))}")
    if one.id in world.companions:
        parts.append("  travels with the player")
    if where and (seen := world.last_seen(one.id)):
        parts.append(f"  last seen in: {seen}")
    return "\n".join(parts)


def thread_lines(threads: Iterable[Thread], *, standing_only: bool) -> str:
    shown = [one for one in threads if one.status != "resolved" or not standing_only]
    return (
        "\n".join(
            # A status is worth a word only when it is not the ordinary one.
            f"- {one.title}[{one.id}]{'' if one.status == 'active' else f' — {one.status}'}"
            f" — {one.note}"
            for one in shown
        )
        or "- (none)"
    )


def subject_of[S: BaseModel](one: Entity[S]) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def narrator_view[S: BaseModel](world: SceneState[S]) -> NarratorView:
    scene = world.current
    here = [one for one in world.here() if one.known]
    cast = [one for one in here if one.kind == "actor"]
    return NarratorView(
        place=scene.place,
        title=scene.title,
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


def player_view[S: BaseModel](state: Game, rows: SheetRows, over: str | None) -> PlayerView:
    world = state.world
    player = world.player
    pending = state.pending
    return PlayerView(
        player=subject_of(player),
        sheet=rows(player.id),
        traits=tuple((one.name, one.text) for one in player.traits),
        carrying=tuple(subject_of(one) for one in world.carried_by(player.id) if one.known),
        present=tuple(subject_of(one) for one in world.here() if one.known and one.id != player.id),
        companions=tuple(world.require(one).name for one in world.companions),
        threads=tuple(
            (one.title, one.status) for one in world.threads.values() if one.status != "resolved"
        ),
        scenes=tuple(one.title for one in (*world.played, world.current)),
        prompt=None
        if pending is None
        else PlayerPrompt(
            prompt=pending.prompt,
            options=tuple(
                DecisionOption(id=one.id, label=one.label, detail=one.detail)
                for one in pending.options
            ),
            allows_text=pending.allows_text,
        ),
        over=over,
    )


def _lines[S: BaseModel](
    world: SceneState[S], entities: Iterable[Entity[S]], rows: SheetRows
) -> str:
    return "\n".join(entity_line(world, one, rows) for one in entities) or "- (none)"


def director_view(state: Game, rows: SheetRows, engine_sections: EngineSections) -> DirectorView:
    """Every section stated, hidden canon included: the game master reads all of it."""
    world = state.world
    scene = world.current
    player = world.player
    return DirectorView(
        sections=(
            ("SCENE", f"{scene.title}\n{scene.situation}"),
            ("YOU PLAY FOR", entity_line(world, player, rows)),
            ("CARRYING", _lines(world, world.carried_by(player.id), rows)),
            (
                "HERE WITH THE PLAYER",
                _lines(world, (one for one in world.here() if one.id != player.id), rows),
            ),
            (
                "HIDDEN HERE (the player has not found these)",
                _lines(world, (world.require(one) for one in scene.hidden), rows),
            ),
            ("ACTIVE THREADS", thread_lines(world.threads.values(), standing_only=True)),
            *engine_sections(state),
            ("SCENE NOTE (never narrate this)", scene.note or "(none)"),
        )
    )
