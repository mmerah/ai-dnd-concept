"""The four ways an item changes hands."""

from ...domain.models import (
    Entity,
    EntityCreated,
    EntityId,
    Event,
    ItemDestination,
    ItemEntity,
    ItemMoved,
    LocationEntity,
    slug,
)
from . import common
from .resolution import Resolution


def take(ctx: Resolution, item_id: EntityId) -> list[Event]:
    item = ctx.of_kind(item_id, ItemEntity)
    player = ctx.player
    if item.container_id != player.location_id:
        raise ValueError(f"cannot take {item_id!r}: it is not at the player's location")
    return [*common.reveal(item), _moved(item, player.id, player.name, "actor")]


def drop(ctx: Resolution, item_id: EntityId) -> list[Event]:
    item = ctx.held(item_id, "drop")
    here = ctx.of_kind(ctx.player.location_id, LocationEntity)
    return [_moved(item, here.id, here.name, "location")]


def give(ctx: Resolution, item_id: EntityId, actor_id: EntityId) -> list[Event]:
    item = ctx.held(item_id, "give")
    if actor_id == ctx.player.id:
        raise ValueError("cannot give an item to the player: they already hold it")
    actor = ctx.actor_here(actor_id)
    return [_moved(item, actor.id, actor.name, "actor")]


def improvise(ctx: Resolution, item_name: str) -> list[Event]:
    """An improvised item is promoted to canon first, so an inventory only ever holds real ids."""
    player = ctx.player
    item = ItemEntity(
        id=slug(item_name, ctx.state.world.entities.keys()),
        name=item_name,
        brief=item_name,  # improvised: the brief is just the written-out name
        container_id=player.location_id,  # created lying here, then picked up
        known=True,
        authored=False,
    )
    return [EntityCreated(entity=item), _moved(item, player.id, player.name, "actor")]


def _moved(item: Entity, to_id: EntityId, to_name: str, to_kind: ItemDestination) -> ItemMoved:
    return ItemMoved(
        item_id=item.id, item_name=item.name, to_id=to_id, to_name=to_name, to_kind=to_kind
    )
