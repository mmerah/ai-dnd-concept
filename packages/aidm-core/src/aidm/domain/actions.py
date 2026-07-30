from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal, TypeGuard, assert_never

from pydantic import Field

from ..utils.models import Frozen
from .base import PLAYER_ID, EntityId, Kind, slug
from .engine import EngineData
from .entities import ActorEntity, Entity, ItemEntity, LocationEntity
from .events import ActorMoved, EntityCreated, EntityDiscovered, Event, ItemMoved
from .state import GameState


@dataclass(frozen=True, slots=True)
class EntityReference:
    kind: Kind | None
    present: bool = False


class CoreAction(Frozen):
    GUIDANCE: ClassVar[str] = ""

    def check(self) -> str | None:
        return None


class Discover(CoreAction):
    """Reveal an existing canon entity to the player."""

    GUIDANCE: ClassVar[str] = """Use when the player's action reveals something from the \
unrevealed list: they notice it, are told of it, or reach it. Prefer this over inventing a \
replacement."""

    action: Literal["discover"] = "discover"
    entity_id: Annotated[EntityId, EntityReference(None)] = Field(
        description="Exact id of the existing canon entity to reveal."
    )


class Move(CoreAction):
    """Move the player or another actor to an existing location."""

    GUIDANCE: ClassVar[str] = """Use when an actor actually changes location. Omit `actor_id` to \
move the player. Moving the player to an unrevealed location discovers it."""

    action: Literal["move"] = "move"
    location_id: Annotated[EntityId, EntityReference("location")] = Field(
        description="Exact id of the canon location the actor enters."
    )
    actor_id: Annotated[EntityId | None, EntityReference("actor")] = Field(
        default=None,
        description="Exact id of the actor to move; omit to move the player.",
    )


class TakeItem(CoreAction):
    """Move a loose canon item at the current location into the player's inventory."""

    GUIDANCE: ClassVar[str] = """Use when the player takes an existing item shown at their current \
location. The item is discovered automatically if it was unrevealed."""

    action: Literal["take_item"] = "take_item"
    item_id: Annotated[EntityId, EntityReference("item")] = Field(
        description="Exact id of a loose canon item at the player's location."
    )


class DropItem(CoreAction):
    """Leave a carried item at the player's current location."""

    GUIDANCE: ClassVar[str] = """Use when the player puts down, abandons, or otherwise stops \
carrying an item in their inventory."""

    action: Literal["drop_item"] = "drop_item"
    item_id: Annotated[EntityId, EntityReference("item")] = Field(
        description="Exact id of an item the player currently carries."
    )


class GiveItem(CoreAction):
    """Transfer a carried item to another actor who is here."""

    GUIDANCE: ClassVar[str] = """Use when the player hands an inventory item to another actor at \
their location. The receiving actor then carries it."""

    action: Literal["give_item"] = "give_item"
    item_id: Annotated[EntityId, EntityReference("item")] = Field(
        description="Exact id of an item the player currently carries."
    )
    actor_id: Annotated[EntityId, EntityReference("actor", present=True)] = Field(
        description="Exact id of the receiving actor here with the player."
    )

    def check(self) -> str | None:
        if self.actor_id == PLAYER_ID:
            return "give_item must name another actor"
        return None


class GainImprovisedItem(CoreAction):
    """Give the player a minor incidental item that has no canon entry."""

    GUIDANCE: ClassVar[str] = """Use only for an ordinary incidental object that is not already in \
canon and is not important enough for the Maintainer and Creator to develop. Never use it as a \
substitute for an existing item."""

    action: Literal["gain_improvised_item"] = "gain_improvised_item"
    item_name: str = Field(
        min_length=1,
        description="The incidental item written out, such as 'a handful of gravel'.",
    )


type CoreActionUnion = Discover | Move | TakeItem | DropItem | GiveItem | GainImprovisedItem
CORE_ACTION_TYPES: tuple[type[CoreAction], ...] = (
    Discover,
    Move,
    TakeItem,
    DropItem,
    GiveItem,
    GainImprovisedItem,
)


class CoreActionRejected(ValueError):
    pass


type CreatedEntityRules = Callable[[Entity, GameState], EngineData | None]


def is_core_action(value: object) -> TypeGuard[CoreActionUnion]:
    return isinstance(
        value,
        Discover | Move | TakeItem | DropItem | GiveItem | GainImprovisedItem,
    )


def action_references(action: CoreActionUnion) -> tuple[tuple[EntityId, EntityReference], ...]:
    references: list[tuple[EntityId, EntityReference]] = []
    for name, field in type(action).model_fields.items():
        marker = next(
            (item for item in field.metadata if isinstance(item, EntityReference)),
            None,
        )
        if marker is None:
            continue
        value = getattr(action, name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise TypeError(f"{type(action).__name__}.{name} is not an entity id")
        references.append((EntityId(value), marker))
    return tuple(references)


def resolve_core_action(
    action: CoreActionUnion,
    state: GameState,
    rules_for_created_entity: CreatedEntityRules,
) -> list[Event]:
    match action:
        case Discover(entity_id=entity_id):
            return _reveal(state.world.require(entity_id))
        case Move():
            return _move(action, state)
        case TakeItem():
            return _take(action, state)
        case DropItem():
            return _drop(action, state)
        case GiveItem():
            return _give(action, state)
        case GainImprovisedItem():
            return _improvise(action, state, rules_for_created_entity)
    assert_never(action)


def _reveal(entity: Entity) -> list[Event]:
    return [] if entity.known else [EntityDiscovered(entity_id=entity.id, name=entity.name)]


def _move(action: Move, state: GameState) -> list[Event]:
    world = state.world
    destination = world.require_kind(action.location_id, LocationEntity)
    player = state.player
    if action.actor_id is None or action.actor_id == PLAYER_ID:
        return [
            *_reveal(destination),
            ActorMoved(
                actor_id=player.id,
                actor_name=player.name,
                location_id=destination.id,
                location_name=destination.name,
            ),
        ]
    actor = world.require_kind(action.actor_id, ActorEntity)
    if actor.location_id != player.location_id and destination.id != player.location_id:
        raise CoreActionRejected(f"cannot move {actor.id!r}: the player would not witness it")
    return [
        *(_reveal(actor) if destination.id == player.location_id else []),
        ActorMoved(
            actor_id=actor.id,
            actor_name=actor.name,
            location_id=destination.id,
            location_name=destination.name,
        ),
    ]


def _take(action: TakeItem, state: GameState) -> list[Event]:
    item = state.world.require_kind(action.item_id, ItemEntity)
    player = state.player
    if item.container_id != player.location_id:
        raise CoreActionRejected(f"cannot take {item.id!r}: it is not at the player's location")
    return [
        *_reveal(item),
        ItemMoved(
            item_id=item.id,
            item_name=item.name,
            to_id=PLAYER_ID,
            to_name=player.name,
            to_kind="actor",
        ),
    ]


def _held(item_id: EntityId, state: GameState, verb: str) -> ItemEntity:
    item = state.world.require_kind(item_id, ItemEntity)
    if item.container_id != PLAYER_ID:
        raise CoreActionRejected(f"cannot {verb} {item.id!r}: the player does not carry it")
    return item


def _drop(action: DropItem, state: GameState) -> list[Event]:
    item = _held(action.item_id, state, "drop")
    location = state.world.require_kind(state.player.location_id, LocationEntity)
    return [
        ItemMoved(
            item_id=item.id,
            item_name=item.name,
            to_id=location.id,
            to_name=location.name,
            to_kind="location",
        )
    ]


def _give(action: GiveItem, state: GameState) -> list[Event]:
    item = _held(action.item_id, state, "give")
    actor = state.world.require_kind(action.actor_id, ActorEntity)
    if actor.id == PLAYER_ID:
        raise CoreActionRejected("cannot give an item to the player: they already hold it")
    if actor.location_id != state.player.location_id:
        raise CoreActionRejected(f"cannot give to {actor.id!r}: they are not here")
    return [
        ItemMoved(
            item_id=item.id,
            item_name=item.name,
            to_id=actor.id,
            to_name=actor.name,
            to_kind="actor",
        )
    ]


def _improvise(
    action: GainImprovisedItem,
    state: GameState,
    rules_for_created_entity: CreatedEntityRules,
) -> list[Event]:
    player = state.player
    item = ItemEntity(
        id=slug(action.item_name, state.world.entities),
        name=action.item_name,
        brief=action.item_name,
        known=True,
        authored=False,
        container_id=player.location_id,
    )
    item = ItemEntity.model_validate(
        item.model_dump() | {"rules": rules_for_created_entity(item, state)}
    )
    return [
        EntityCreated(entity=item),
        ItemMoved(
            item_id=item.id,
            item_name=item.name,
            to_id=player.id,
            to_name=player.name,
            to_kind="actor",
        ),
    ]
