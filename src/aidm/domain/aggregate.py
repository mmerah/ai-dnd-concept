from typing import Self

from pydantic import BaseModel

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap, updated
from .base import EntityId


class EngineAggregate[ActorState: BaseModel, ItemState: BaseModel](Frozen):
    """An engine's id-keyed side table; the commit validator keeps its keys tracking the world."""

    actors: FrozenMap[EntityId, ActorState] = EMPTY_FROZEN_MAP
    items: FrozenMap[EntityId, ItemState] = EMPTY_FROZEN_MAP

    def actor(self, actor_id: EntityId) -> ActorState:
        state = self.actors.get(actor_id)
        if state is None:
            raise ValueError(f"{type(self).__name__} holds no actor {actor_id!r}")
        return state

    def item(self, item_id: EntityId) -> ItemState:
        state = self.items.get(item_id)
        if state is None:
            raise ValueError(f"{type(self).__name__} holds no item {item_id!r}")
        return state

    def with_actor(self, actor_id: EntityId, state: ActorState) -> Self:
        return updated(self, actors={**self.actors, actor_id: state})

    def with_item(self, item_id: EntityId, state: ItemState) -> Self:
        return updated(self, items={**self.items, item_id: state})
