from aidm.domain.base import EntityId, slug
from aidm.domain.entities import ItemEntity, LocationEntity
from aidm.domain.events import EntityCreated, ItemDestination, ItemMoved

from ...domain.models.consequences import (
    DropItem,
    GainImprovisedItem,
    GiveItem,
    TakeItem,
)
from ...domain.models.events import Dnd5eEvent
from . import common
from .resolution import Resolution


def take(ctx: Resolution, consequence: TakeItem) -> list[Dnd5eEvent]:
    item = ctx.of_kind(consequence.item_id, ItemEntity)
    player = ctx.player
    if item.container_id != player.location_id:
        raise ValueError(f"cannot take {item.id!r}: it is not at the player's location")
    return [*common.reveal(item), _moved(item, player.id, player.name, "actor")]


def drop(ctx: Resolution, consequence: DropItem) -> list[Dnd5eEvent]:
    item = ctx.held(consequence.item_id, "drop")
    here = ctx.of_kind(ctx.player.location_id, LocationEntity)
    return [_moved(item.entity, here.id, here.name, "location")]


def give(ctx: Resolution, consequence: GiveItem) -> list[Dnd5eEvent]:
    item = ctx.held(consequence.item_id, "give")
    if consequence.actor_id == ctx.player.id:
        raise ValueError("cannot give an item to the player: they already hold it")
    actor = ctx.actor_here(consequence.actor_id)
    return [_moved(item.entity, actor.id, actor.name, "actor")]


def improvise(ctx: Resolution, consequence: GainImprovisedItem) -> list[Dnd5eEvent]:
    """Promote improvised items so inventories contain only canon IDs."""
    player = ctx.player
    written = consequence.item_name
    item = ItemEntity(
        id=slug(written, ctx.state.world.entities.keys()),
        name=written,
        brief=written,
        container_id=player.location_id,
        known=True,
        authored=False,
    )
    return [EntityCreated(entity=item), _moved(item, player.id, player.name, "actor")]


def _moved(
    item: ItemEntity, to_id: EntityId, to_name: str, to_kind: ItemDestination
) -> ItemMoved:
    return ItemMoved(
        item_id=item.id, item_name=item.name, to_id=to_id, to_name=to_name, to_kind=to_kind
    )
