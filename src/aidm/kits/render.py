from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel

from aidm.core.entities import EntityId
from aidm.core.model import AnyGame, Game
from aidm.core.play import DecisionOption
from aidm.core.views import PlayerPrompt, Subject
from aidm.kits.entities import Entity, Thread, World

# The engine's own sheet rows for one entity; empty for scenery nothing rolls against.
type SheetRows = Callable[[EntityId], tuple[tuple[str, str], ...]]
# Sections only the engine can state, such as the advances it owes the party.
type EngineSections[G: Game[Any]] = Callable[[G], tuple[tuple[str, str], ...]]


def subject_of[S: BaseModel](one: Entity[S]) -> Subject:
    return Subject(id=one.id, name=one.name, brief=one.brief)


def entity_line[S: BaseModel](
    world: World[S], one: Entity[S], rows: SheetRows, *, detail: str = ""
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
    if detail:
        parts.append(f"  {detail}")
    return "\n".join(parts)


def entity_lines[S: BaseModel](
    world: World[S], entities: Iterable[Entity[S]], rows: SheetRows
) -> str:
    return "\n".join(entity_line(world, one, rows) for one in entities) or "- (none)"


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


def player_prompt(state: AnyGame) -> PlayerPrompt | None:
    pending = state.pending
    return (
        None
        if pending is None
        else PlayerPrompt(
            kind=pending.kind,
            prompt=pending.prompt,
            options=tuple(
                DecisionOption(id=one.id, label=one.label, detail=one.detail)
                for one in pending.options
            ),
            allows_text=pending.allows_text,
        )
    )
