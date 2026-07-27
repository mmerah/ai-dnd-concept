"""Renderers for single context fragments. Pure string in, pure string out."""

from collections.abc import Iterable, Sequence

from ..domain.models import (
    PLAYER_ID,
    ActorEntity,
    Direction,
    Entity,
    EntityId,
    Exchange,
    GameState,
    GrowthRequest,
    ItemEntity,
    LocationEntity,
    find,
)


def label(e: Entity) -> str:
    """Every entity is shown as `name[id=...]`, so any role can reference it by the id it must use.
    A prose-only role ignores the bracket; a role that emits ids reads it off directly."""
    return f"{e.name}[id={e.id}]"


def canon_without_player(state: GameState) -> list[Entity]:
    """Every list a role is shown subtracts the player: canon, but never a role's target."""
    return [e for e in state.world.entities.values() if e.id != PLAYER_ID]


def _item_holder(state: GameState, item_id: EntityId) -> ActorEntity | None:
    actors = (e for e in state.world.entities.values() if isinstance(e, ActorEntity))
    return next((e for e in actors if item_id in e.inventory), None)


def _place(entity: Entity, state: GameState) -> tuple[EntityId | None, str]:
    """Where to file an entity, and the suffix that says so. A carried item travels with its
    holder, so it stays in context once picked up rather than dropping to a bare name."""
    entities = state.world.entities
    match entity:
        case LocationEntity():
            return None, ""
        case ActorEntity():
            place = entities.get(entity.location_id)
            return entity.location_id, f" — at {place.name}" if place else ""
        case ItemEntity():
            if entity.location_id is not None:
                place = entities.get(entity.location_id)
                return entity.location_id, f" — at {place.name}" if place else ""
            holder = _item_holder(state, entity.id)
            if holder is None:
                raise ValueError(f"cannot place item {entity.id!r}: nobody holds it")
            if holder.id == PLAYER_ID:
                return holder.location_id, " — carried"
            return holder.location_id, f" — held by {holder.name}"


def briefs(items: Iterable[Entity], state: GameState) -> str:
    return (
        "\n".join(f"- {label(e)} — {e.kind}{_place(e, state)[1]} — {e.brief}" for e in items)
        or "- (none)"
    )


def present(state: GameState) -> list[Entity]:
    """Everything filed at the player's location; their own items show under CHARACTER."""
    where = state.player.location_id
    carried = set(state.player.inventory)
    return [
        e
        for e in canon_without_player(state)
        if e.id not in carried and _place(e, state)[0] == where
    ]


def here(state: GameState) -> str:
    return briefs((e for e in present(state) if e.known), state)


def elsewhere(state: GameState) -> str:
    """Known entities away from here; the current location and carried items show elsewhere."""
    here_ids = {e.id for e in present(state)}
    current = state.player.location_id
    carried = set(state.player.inventory)

    def shown(e: Entity) -> bool:
        return e.known and e.id not in here_ids and e.id != current and e.id not in carried

    return briefs((e for e in canon_without_player(state) if shown(e)), state)


def unrevealed(state: GameState) -> str:
    return briefs((e for e in canon_without_player(state) if not e.known), state)


def catalogue(state: GameState) -> str:
    return briefs(canon_without_player(state), state)


def character(state: GameState) -> str:
    """The player's own sheet, and the one place exact hit points are shown. Fail fast: standing
    outside canon, or holding an id no entity backs, would feed a role an unusable reference."""
    player = state.player
    where = find(state.world.entities, player.location_id)
    if where is None:
        raise ValueError(f"character is at unknown location {player.location_id!r}")
    stats = player.stats
    attributes = ", ".join(f"{k} {v}" for k, v in stats.attributes.model_dump().items())
    items = [find(state.world.entities, i) for i in player.inventory]
    missing = [i for i, e in zip(player.inventory, items, strict=True) if e is None]
    if missing:
        raise ValueError(f"character holds unknown item id(s) {missing!r}")
    inventory = "\n".join(f"- {label(e)} — {e.brief}" for e in items if e is not None) or "- (none)"
    return (
        f"{player.name} — hp {stats.hp}/{stats.max_hp} — at {label(where)}\n"
        f"attributes: {attributes}\ninventory:\n{inventory}"
    )


def history(recent: Sequence[Exchange]) -> str:
    return "\n\n".join(f"Player: {x.prompt}\nDM: {x.narration}" for x in recent) or "(nothing yet)"


def speaker(state: GameState, direction: Direction) -> str:
    """Fail fast: a hidden, unknown, or absent speaker would put words in a stranger's mouth."""
    if direction.speaker_id is None:
        return "(none — narrate the scene)"
    entity = find(state.world.entities, direction.speaker_id)
    if entity is None or not entity.known or entity.id == PLAYER_ID:
        raise ValueError(f"director named an unknown or hidden speaker: {direction.speaker_id!r}")
    if _place(entity, state)[0] != state.player.location_id:
        raise ValueError(f"director named a speaker who is not here: {direction.speaker_id!r}")
    return f"{label(entity)} — {entity.brief}"


def request(item: GrowthRequest) -> str:
    where = f"\nlocation: {item.location}" if item.location else ""
    return f"a {item.kind} named {item.name}\nbrief: {item.brief}{where}"
