from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from aidm.core.entities import DEAD, CheckedEntityId, EntityId, Frozen, Trait
from aidm.core.facts import Fact
from aidm.core.model import Game
from aidm.core.tools import MasterTool, master_tool
from aidm.kits.entities import Entity, entity_fact
from aidm.kits.rooms.state import RoomVisit, RoomWorld
from aidm.kits.verbs import (
    CHANGE_WORLD,
    TO_PLAYER,
    AddTrait,
    AdvanceThread,
    ImproviseItem,
    JoinParty,
    Kill,
    LeaveParty,
    RemoveTrait,
    Reveal,
    add_trait,
    advance_thread,
    improvise_item,
    join_party,
    leave_party,
    remove_trait,
    reveal,
)

TO_PLACE = "place"


class MoveItem(Frozen):
    """Move an item: to the player, to someone here, or loose in this place."""

    verb: Literal["move_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item here or carried.")
    to: CheckedEntityId = Field(description="`player`, `place`, or the exact id of an actor here.")


WorldChange = (
    Reveal
    | MoveItem
    | ImproviseItem
    | AddTrait
    | RemoveTrait
    | Kill
    | JoinParty
    | LeaveParty
    | AdvanceThread
)


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb", description="The one world change to apply; `verb` picks the change."
    )


class Move(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the place to move to.")


class UnlockWay(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the locked way's destination.")


def apply_change[S: BaseModel](
    world: RoomWorld[S], change: WorldChange, default_sheet: Callable[[], S | None]
) -> list[Fact]:
    match change:
        case Reveal():
            return reveal(world, _acted_on(world, change.entity_id))
        case MoveItem():
            return _move_item(world, change)
        case ImproviseItem():
            _item, facts = improvise_item(world, change, default_sheet)
            return facts
        case AddTrait():
            return add_trait(world, _acted_on(world, change.entity_id), change)
        case RemoveTrait():
            return remove_trait(world, _acted_on(world, change.entity_id), change)
        case Kill():
            return _kill(world, change.actor_id)
        case JoinParty():
            return join_party(world, change)
        case LeaveParty():
            return leave_party(world, change)
        case AdvanceThread():
            return advance_thread(world, change)


def move[S: BaseModel](world: RoomWorld[S], to_id: EntityId) -> list[Fact]:
    here = world.current
    destination = world.require_kind(to_id, "place")
    way = world.way(here.id, destination.id)
    if way is None:
        options = (
            ", ".join(world.require(one.to).name for one in world.ways.get(here.id, ())) or "(none)"
        )
        raise ValueError(
            f"no way leads from {here.name} to {destination.name}; ways out: {options}"
        )
    if way.locked:
        raise ValueError(f"the way to {destination.name} is locked and must be dealt with first")
    way.known = True
    if back := world.way(destination.id, here.id):
        back.known = True
    facts = world.reveal(destination)
    world.player.carried_by = destination.id
    for member_id in world.companions:
        world.require_kind(member_id, "actor").carried_by = destination.id
    world.visits.append(RoomVisit(place=destination.id))
    facts.append(
        entity_fact(
            destination,
            "arrived",
            f"the player arrives at {destination.name}[{destination.id}]",
            card=f"Arrived at {destination.name}",
        )
    )
    return facts


def unlock_way[S: BaseModel](world: RoomWorld[S], to_id: EntityId) -> list[Fact]:
    here = world.current
    destination = world.require_kind(to_id, "place")
    way = world.way(here.id, destination.id)
    if way is None:
        raise ValueError(f"no way leads from {here.name} to {destination.name}")
    if not way.locked:
        raise ValueError(f"the way from {here.name} to {destination.name} is not locked")
    way.locked = False
    return [
        entity_fact(
            here,
            "way_unlocked",
            f"the way from {here.name}[{here.id}] to "
            f"{destination.name}[{destination.id}] is unlocked",
            narrate=way.known and here.known,
            card=f"{destination.name} unlocked",
        )
    ]


def room_tools[G: Game[Any], S: BaseModel](
    world_of: Callable[[G], RoomWorld[S]], default_sheet: Callable[[], S | None]
) -> tuple[MasterTool[G], ...]:
    change_world: MasterTool[G] = master_tool(
        "change_world",
        CHANGE_WORLD,
        ChangeWorld,
        lambda draft, one, _rng: apply_change(world_of(draft), one.change, default_sheet),
        during_suspension=True,
    )
    movement: MasterTool[G] = master_tool(
        "move",
        "Move through an unlocked way from the player's current place.",
        Move,
        lambda draft, one, _rng: move(world_of(draft), one.to_id),
    )
    unlock: MasterTool[G] = master_tool(
        "unlock_way",
        "Unlock a locked way out of the player's current place.",
        UnlockWay,
        lambda draft, one, _rng: unlock_way(world_of(draft), one.to_id),
        during_suspension=True,
    )
    return change_world, movement, unlock


def _move_item[S: BaseModel](world: RoomWorld[S], change: MoveItem) -> list[Fact]:
    item = world.require_kind(change.item_id, "item")
    location = world.location_of(item)
    if location is None or location.id != world.current.id:
        raise ValueError(f"{item.name} is not here, and nobody here is carrying it")
    target = change.to
    holder_id = (
        world.player_id
        if target == TO_PLAYER
        else world.current.id
        if target == TO_PLACE
        else EntityId(target)
    )
    if target not in (TO_PLAYER, TO_PLACE):
        world.require_actor_here(holder_id)
    if item.carried_by == holder_id:
        raise ValueError(f"{item.name} is already held by {target}")
    seen = world.reveal(item)
    item.carried_by = holder_id
    trace = f"{world.label(item)} moves to {world.label(world.require(holder_id))}"
    return [*seen, entity_fact(item, "entity_moved", trace, card=f"Moved {item.name}")]


def _kill[S: BaseModel](world: RoomWorld[S], actor_id: EntityId) -> list[Fact]:
    actor = world.require_actor_here(actor_id)
    if actor.trait(DEAD) is not None:
        raise ValueError(f"{actor.name} is already dead")
    facts = world.reveal(actor)
    if actor.id in world.companions:
        world.companions.remove(actor.id)
    actor.traits.append(Trait(id=DEAD, name="Dead"))
    dropped = list(world.carried_by(actor.id))
    for item in dropped:
        item.carried_by = world.current.id
    if dropped:
        facts.append(
            Fact(
                kind="items_dropped",
                trace=", ".join(world.label(item) for item in dropped) + " fell loose here",
            )
        )
    facts.append(
        entity_fact(
            actor, "actor_killed", f"{world.label(actor)} is dead", card=f"{actor.name} is dead"
        )
    )
    return facts


def _acted_on[S: BaseModel](world: RoomWorld[S], entity_id: EntityId) -> Entity[S]:
    entity = world.require(entity_id)
    if entity.kind == "actor":
        return world.require_actor_here(entity_id)
    if world.location_of(entity) != world.current:
        raise ValueError(f"{entity.name} is not here with the player")
    return entity
