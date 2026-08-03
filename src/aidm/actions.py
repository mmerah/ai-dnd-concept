from collections.abc import Callable
from typing import Annotated, Literal, TypeGuard, assert_never

from pydantic import Field

from .base import PLAYER_ID, Entity, EntityId, slug
from .content import Rules
from .directing import ConsequenceBase, Reference
from .facts import Fact
from .world import GameState

_NOT_CARRIED = "the player does not carry it"


class Discover(ConsequenceBase):
    """Reveal an existing canon entity to the player."""

    GUIDANCE = """Use when the player's action reveals something from the unrevealed list: they \
notice it, are told of it, or reach it. Prefer this over inventing a replacement."""

    action: Literal["discover"] = "discover"
    entity_id: Annotated[EntityId, Reference(None)] = Field(
        description="Exact id of the existing canon entity to reveal."
    )


class Move(ConsequenceBase):
    """Move the player or another actor to an existing location."""

    GUIDANCE = """Use when an actor actually changes location. Omit `actor_id` to move the player. \
Moving the player to an unrevealed location discovers it."""

    action: Literal["move"] = "move"
    location_id: Annotated[EntityId, Reference("location")] = Field(
        description="Exact id of the canon location the actor enters."
    )
    actor_id: Annotated[EntityId | None, Reference("actor")] = Field(
        default=None,
        description="Exact id of the actor to move; omit to move the player.",
    )


class TakeItem(ConsequenceBase):
    """Move a loose canon item at the current location into the player's inventory."""

    GUIDANCE = """Use when the player takes an existing item shown at their current location. The \
item is discovered automatically if it was unrevealed."""

    action: Literal["take_item"] = "take_item"
    item_id: Annotated[EntityId, Reference("item")] = Field(
        description="Exact id of a loose canon item at the player's location."
    )


class DropItem(ConsequenceBase):
    """Leave a carried item at the player's current location."""

    GUIDANCE = """Use when the player puts down, abandons, or otherwise stops carrying an item in \
their inventory."""

    action: Literal["drop_item"] = "drop_item"
    item_id: Annotated[EntityId, Reference("item")] = Field(
        description="Exact id of an item the player currently carries."
    )


class GiveItem(ConsequenceBase):
    """Transfer a carried item to another actor who is here."""

    GUIDANCE = """Use when the player hands an inventory item to another actor at their location. \
The receiving actor then carries it."""

    action: Literal["give_item"] = "give_item"
    item_id: Annotated[EntityId, Reference("item")] = Field(
        description="Exact id of an item the player currently carries."
    )
    actor_id: Annotated[EntityId, Reference("actor", present=True)] = Field(
        description="Exact id of the receiving actor here with the player."
    )

    def check(self) -> str | None:
        if self.actor_id == PLAYER_ID:
            return "give_item must name another actor: the player already holds the item"
        return None


class GainImprovisedItem(ConsequenceBase):
    """Give the player a minor incidental item that has no canon entry."""

    GUIDANCE = """Use only for an ordinary incidental object that is not already in canon and is \
not important enough for the Maintainer and Creator to develop. Never use it as a substitute for \
an existing item."""

    action: Literal["gain_improvised_item"] = "gain_improvised_item"
    item_name: str = Field(
        min_length=1,
        description="The incidental item written out, such as 'a handful of gravel'.",
    )


type WorldAction = Discover | Move | TakeItem | DropItem | GiveItem | GainImprovisedItem
WORLD_ACTION_TYPES: tuple[type[ConsequenceBase], ...] = (
    Discover,
    Move,
    TakeItem,
    DropItem,
    GiveItem,
    GainImprovisedItem,
)


class WorldActionRejected(ValueError):
    pass


def is_world_action(value: object) -> TypeGuard[WorldAction]:
    return isinstance(value, Discover | Move | TakeItem | DropItem | GiveItem | GainImprovisedItem)


def resolve_world_action(
    action: WorldAction,
    draft: GameState,
    improvised_item_rules: Callable[[], Rules],
) -> list[Fact]:
    match action:
        case Discover(entity_id=entity_id):
            return draft.reveal(draft.world.require(entity_id))
        case Move():
            return _move(action, draft)
        case TakeItem():
            return _take(action, draft)
        case DropItem():
            return _drop(action, draft)
        case GiveItem():
            return _give(action, draft)
        case GainImprovisedItem():
            return _improvise(action, draft, improvised_item_rules)
    assert_never(action)


def _move(action: Move, draft: GameState) -> list[Fact]:
    destination = draft.world.require_kind(action.location_id, "location")
    here = draft.player_location
    if action.actor_id is None or action.actor_id == PLAYER_ID:
        return [*draft.reveal(destination), draft.move(draft.player, destination)]
    actor = draft.world.require_kind(action.actor_id, "actor")
    if actor.parent_id != here and destination.id != here:
        raise WorldActionRejected(f"cannot move {actor.id!r}: the player would not witness it")
    revealed = draft.reveal(actor) if destination.id == here else []
    return [*revealed, draft.move(actor, destination)]


def _relocate(
    draft: GameState,
    item_id: EntityId,
    *,
    origin: EntityId,
    destination: Entity,
    requirement: str,
) -> list[Fact]:
    """The player has seen any item they may move, so one reveal serves all three actions."""
    item = draft.world.require_kind(item_id, "item")
    if item.parent_id != origin:
        raise WorldActionRejected(f"cannot move {item.id!r}: {requirement}")
    return [*draft.reveal(item), draft.move(item, destination)]


def _take(action: TakeItem, draft: GameState) -> list[Fact]:
    return _relocate(
        draft,
        action.item_id,
        origin=draft.player_location,
        destination=draft.player,
        requirement="it is not at the player's location",
    )


def _drop(action: DropItem, draft: GameState) -> list[Fact]:
    return _relocate(
        draft,
        action.item_id,
        origin=PLAYER_ID,
        destination=draft.world.require_kind(draft.player_location, "location"),
        requirement=_NOT_CARRIED,
    )


def _give(action: GiveItem, draft: GameState) -> list[Fact]:
    actor = draft.world.require_kind(action.actor_id, "actor")
    if actor.id == PLAYER_ID:
        raise WorldActionRejected("cannot give an item to the player: they already hold it")
    if actor.parent_id != draft.player_location:
        raise WorldActionRejected(
            f"cannot give to {actor.id!r}: they are not at the player's location"
        )
    return _relocate(
        draft,
        action.item_id,
        origin=PLAYER_ID,
        destination=actor,
        requirement=_NOT_CARRIED,
    )


def _improvise(
    action: GainImprovisedItem,
    draft: GameState,
    improvised_item_rules: Callable[[], Rules],
) -> list[Fact]:
    item = Entity(
        id=slug(action.item_name, draft.world.all_ids()),
        kind="item",
        name=action.item_name,
        brief=action.item_name,
        known=True,
        parent_id=draft.player_location,
    )
    created = draft.add(item, improvised_item_rules())
    return [created, draft.move(item, draft.player)]
