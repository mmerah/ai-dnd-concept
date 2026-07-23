"""Renderers for single context fragments. Pure string in, pure string out."""

from collections.abc import Sequence

from ..config import settings
from ..domain.models import Direction, Entity, GameState, GrowthRequest, find, find_by_name


def character(state: GameState) -> str:
    c = state.character
    attributes = ", ".join(f"{k} {v}" for k, v in c.attributes.model_dump().items())
    inventory = ", ".join(c.inventory) or "empty"
    return (
        f"{c.name} — hp {c.hp}/{c.max_hp} — at {c.location}\n"
        f"attributes: {attributes}\ninventory: {inventory}"
    )


def briefs(items: Sequence[Entity]) -> str:
    return "\n".join(f"- {e.name} — {e.kind} — {e.brief}" for e in items) or "- (none)"


def briefs_with_ids(items: Sequence[Entity]) -> str:
    """Only the Director sees ids; it needs them to fill `speaker_id`."""
    return "\n".join(f"- {e.name} — {e.kind}, id={e.id} — {e.brief}" for e in items) or "- (none)"


def history(state: GameState) -> str:
    recent = state.history[-settings().history_window :]
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(state: GameState, direction: Direction) -> str:
    """Fail fast: a hallucinated or hidden speaker would put words in a stranger's mouth."""
    if direction.speaker_id is None:
        return "(none — narrate the scene)"
    # the Director reliably answers with a name now and then; that is unambiguous enough to accept
    entity = find(state.scenario, direction.speaker_id) or find_by_name(
        state.scenario, direction.speaker_id
    )
    if entity is None or not entity.known:
        raise ValueError(f"director named an unknown or hidden speaker: {direction.speaker_id!r}")
    return f"{entity.name} — {entity.brief}"


def request(item: GrowthRequest) -> str:
    return f"a {item.kind} named {item.name}\nbrief: {item.brief}"
