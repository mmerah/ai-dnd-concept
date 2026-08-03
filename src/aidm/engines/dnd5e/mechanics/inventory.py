from aidm.base import ItemEntity, LocationEntity, slug

from ..direction import (
    DropItem,
    GainImprovisedItem,
    GiveItem,
    TakeItem,
)
from ..facts import Emitted
from ..state import Dnd5eItemState
from . import common
from .resolution import Resolution


def take(ctx: Resolution, consequence: TakeItem) -> list[Emitted]:
    item = ctx.of_kind(consequence.item_id, ItemEntity)
    player = ctx.player
    if item.container_id != player.location_id:
        raise ValueError(f"cannot take {item.id!r}: it is not at the player's location")
    seen: list[Emitted] = [*common.reveal(ctx, item)]
    return [*seen, ctx.draft.move_item(item, player.entity)]


def drop(ctx: Resolution, consequence: DropItem) -> list[Emitted]:
    item = ctx.held(consequence.item_id, "drop")
    here = ctx.of_kind(ctx.player.location_id, LocationEntity)
    return [ctx.draft.move_item(item.entity, here)]


def give(ctx: Resolution, consequence: GiveItem) -> list[Emitted]:
    item = ctx.held(consequence.item_id, "give")
    if consequence.actor_id == ctx.player.id:
        raise ValueError("cannot give an item to the player: they already hold it")
    actor = ctx.actor_here(consequence.actor_id)
    return [ctx.draft.move_item(item.entity, actor.entity)]


def improvise(ctx: Resolution, consequence: GainImprovisedItem) -> list[Emitted]:
    """Promote improvised items so inventories contain only canon IDs."""
    player = ctx.player
    written = consequence.item_name
    item = ItemEntity(
        id=slug(written, ctx.draft.world.all_ids()),
        name=written,
        brief=written,
        container_id=player.location_id,
        known=True,
    )
    created = ctx.draft.add(item, Dnd5eItemState())
    return [created, ctx.draft.move_item(item, player.entity)]
