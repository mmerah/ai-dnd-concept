from collections.abc import Mapping

from aidm.state.entities import (
    DEAD,
    Entity,
    EntityId,
    Kind,
    require_unique,
)
from aidm.state.model import Game, WorldState

_HOLDERS: Mapping[Kind, tuple[Kind, ...]] = {
    "actor": ("location",),
    "item": ("actor", "location"),
    "location": (),
}


def children(
    world: WorldState, entity_id: EntityId, kind: Kind | None = None
) -> tuple[Entity, ...]:
    held = world.entities.values() if kind is None else world.of_kind(kind)
    return tuple(entity for entity in held if entity.parent_id == entity_id)


def location_of(world: WorldState, entity: Entity) -> EntityId | None:
    """Walk holders up to the enclosing place; a location is inside none, so it has none."""
    current = entity
    while current.parent_id is not None:
        current = world.require(current.parent_id)
    return None if current.id == entity.id else current.id


def player_location(state: Game) -> EntityId:
    location = state.player.parent_id
    if location is None:
        raise ValueError("the player is not in a location")
    return location


def is_here(state: Game, entity: Entity) -> bool:
    return location_of(state.world, entity) == player_location(state)


def walk(entities: Mapping[EntityId, Entity], start: EntityId) -> set[EntityId]:
    reached = {start}
    frontier = [start]
    while frontier:
        here = entities.get(frontier.pop())
        for way in () if here is None else here.exits:
            if way.to not in reached:
                reached.add(way.to)
                frontier.append(way.to)
    return reached


def frontier(world: WorldState) -> int:
    """Unknown locations a known location leads to: doors the player can still find."""
    return len(
        {
            way.to
            for entity in world.entities.values()
            if entity.known
            for way in entity.exits
            if not world.require(way.to).known
        }
    )


def validate_rooms(world: WorldState) -> None:
    """The placement, exit and party rules only a rooms engine gives meaning to."""
    for entity in world.entities.values():
        holder = None if entity.parent_id is None else world.find(entity.parent_id)
        _check_placement(entity, holder)
        _check_exits(world, entity)
    require_unique("party members", world.party)
    for member_id in world.party:
        member = world.require_kind(member_id, "actor")
        if not member.known:
            raise ValueError(f"{member_id!r} travels with the player without being met")
        if member.trait(DEAD) is not None:
            raise ValueError(f"{member_id!r} is dead and cannot travel with the player")


def _check_placement(entity: Entity, holder: Entity | None) -> None:
    allowed = _HOLDERS[entity.kind]
    if not allowed:
        if entity.parent_id is not None:
            raise ValueError(f"{entity.kind} {entity.id!r} cannot be inside anything")
        return
    if holder is None:
        raise ValueError(f"{entity.kind} {entity.id!r} is not in a valid {' or '.join(allowed)}")
    if holder.kind not in allowed:
        raise ValueError(f"{entity.kind} {entity.id!r} is in a {holder.kind}, which cannot hold it")


def _check_exits(world: WorldState, entity: Entity) -> None:
    if entity.exits and entity.kind != "location":
        raise ValueError(f"{entity.kind} {entity.id!r} cannot have exits")
    for way in entity.exits:
        far = world.require_kind(way.to, "location")
        if way.known and not (entity.known and far.known):
            raise ValueError(
                f"the known way from {entity.id!r} to {way.to!r} names a place the player "
                "has not met"
            )
