"""Renderers for single context fragments. Pure string in, pure string out."""

from collections.abc import Iterable, Sequence

from ..domain.models import Direction, Entity, Exchange, GameState, GrowthRequest, find


def label(e: Entity) -> str:
    """Every entity is shown as `name[id=...]`, so any role can reference it by the id it must use.
    A prose-only role ignores the bracket; a role that emits ids reads it off directly."""
    return f"{e.name}[id={e.id}]"


def character(state: GameState) -> str:
    """Fail fast: standing outside canon would offer the Director a location id it cannot use."""
    c = state.character
    where = find(state.world.entities, c.location_id)
    if where is None:
        raise ValueError(f"character is at unknown location {c.location_id!r}")
    attributes = ", ".join(f"{k} {v}" for k, v in c.attributes.model_dump().items())
    inventory = ", ".join(c.inventory) or "empty"
    return (
        f"{c.name} — hp {c.hp}/{c.max_hp} — at {label(where)}\n"
        f"attributes: {attributes}\ninventory: {inventory}"
    )


def briefs(items: Iterable[Entity]) -> str:
    return "\n".join(f"- {label(e)} — {e.kind} — {e.brief}" for e in items) or "- (none)"


def history(recent: Sequence[Exchange]) -> str:
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(state: GameState, direction: Direction) -> str:
    """Fail fast: a hidden or unknown speaker would put words in a stranger's mouth."""
    if direction.speaker_id is None:
        return "(none — narrate the scene)"
    entity = find(state.world.entities, direction.speaker_id)
    if entity is None or not entity.known:
        raise ValueError(f"director named an unknown or hidden speaker: {direction.speaker_id!r}")
    return f"{label(entity)} — {entity.brief}"


def request(item: GrowthRequest) -> str:
    return f"a {item.kind} named {item.name}\nbrief: {item.brief}"
