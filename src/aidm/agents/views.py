"""Renderers for single context fragments. Pure string in, pure string out."""

from collections.abc import Iterable, Sequence

from ..domain.models import (
    Direction,
    Entity,
    EntityId,
    Exchange,
    GameState,
    GrowthRequest,
    ItemEntity,
    LocationEntity,
    NpcEntity,
    find,
)


def label(e: Entity) -> str:
    """Every entity is shown as `name[id=...]`, so any role can reference it by the id it must use.
    A prose-only role ignores the bracket; a role that emits ids reads it off directly."""
    return f"{e.name}[id={e.id}]"


def _item_holder(state: GameState, item_id: EntityId) -> NpcEntity | None:
    """The NPC carrying an item, or None when the player carries it (or it lies loose)."""
    npcs = (e for e in state.world.entities.values() if isinstance(e, NpcEntity))
    return next((e for e in npcs if item_id in e.inventory), None)


def _place(entity: Entity, state: GameState) -> tuple[EntityId | None, str]:
    """Where to file an entity, and the suffix that says so. A carried item travels with its holder
    ("held by <npc>" / "carried"), so an item stays in context once it is picked up rather than
    dropping to a bare name. A location files nowhere; an NPC or a lying item at its location."""
    entities = state.world.entities
    match entity:
        case LocationEntity():
            return None, ""
        case NpcEntity():
            place = entities.get(entity.location_id)
            return entity.location_id, f" — at {place.name}" if place else ""
        case ItemEntity():
            if entity.location_id is not None:
                place = entities.get(entity.location_id)
                return entity.location_id, f" — at {place.name}" if place else ""
            holder = _item_holder(state, entity.id)
            if holder is None:
                return state.character.location_id, " — carried"
            return holder.location_id, f" — held by {holder.name}"


def briefs(items: Iterable[Entity], state: GameState) -> str:
    return (
        "\n".join(f"- {label(e)} — {e.kind}{_place(e, state)[1]} — {e.brief}" for e in items)
        or "- (none)"
    )


def present(state: GameState) -> list[Entity]:
    """Everything filed at the player's location: NPCs, items lying there, and items a present NPC
    carries. The player's own items are shown under CHARACTER, not here."""
    where = state.character.location_id
    carried = set(state.character.inventory)
    return [
        e
        for e in state.world.entities.values()
        if e.id not in carried and _place(e, state)[0] == where
    ]


def here(state: GameState) -> str:
    return briefs((e for e in present(state) if e.known), state)


def elsewhere(state: GameState) -> str:
    """Known entities the player is aware of but not among: NPCs and items away from here (an item
    beside its holder), and other known locations. The current location and the player's own items
    show under CHARACTER."""
    here_ids = {e.id for e in present(state)}
    current = state.character.location_id
    carried = set(state.character.inventory)

    def shown(e: Entity) -> bool:
        return e.known and e.id not in here_ids and e.id != current and e.id not in carried

    return briefs((e for e in state.world.entities.values() if shown(e)), state)


def unrevealed(state: GameState) -> str:
    return briefs((e for e in state.world.entities.values() if not e.known), state)


def catalogue(state: GameState) -> str:
    return briefs(state.world.entities.values(), state)


def character(state: GameState) -> str:
    """Fail fast: standing outside canon, or holding an id no entity backs, would feed the Director
    a reference it cannot use."""
    c = state.character
    where = find(state.world.entities, c.location_id)
    if where is None:
        raise ValueError(f"character is at unknown location {c.location_id!r}")
    attributes = ", ".join(f"{k} {v}" for k, v in c.attributes.model_dump().items())
    items = [find(state.world.entities, i) for i in c.inventory]
    missing = [i for i, e in zip(c.inventory, items, strict=True) if e is None]
    if missing:
        raise ValueError(f"character holds unknown item id(s) {missing!r}")
    inventory = "\n".join(f"- {label(e)} — {e.brief}" for e in items if e is not None) or "- (none)"
    return (
        f"{c.name} — hp {c.hp}/{c.max_hp} — at {label(where)}\n"
        f"attributes: {attributes}\ninventory:\n{inventory}"
    )


def history(recent: Sequence[Exchange]) -> str:
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(state: GameState, direction: Direction) -> str:
    """Fail fast: a hidden, unknown, or absent speaker would put words in a stranger's mouth."""
    if direction.speaker_id is None:
        return "(none — narrate the scene)"
    entity = find(state.world.entities, direction.speaker_id)
    if entity is None or not entity.known:
        raise ValueError(f"director named an unknown or hidden speaker: {direction.speaker_id!r}")
    if _place(entity, state)[0] != state.character.location_id:
        raise ValueError(f"director named a speaker who is not here: {direction.speaker_id!r}")
    return f"{label(entity)} — {entity.brief}"


def request(item: GrowthRequest) -> str:
    where = f"\nlocation: {item.location}" if item.location else ""
    return f"a {item.kind} named {item.name}\nbrief: {item.brief}{where}"
