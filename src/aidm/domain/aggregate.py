from pydantic import BaseModel, Field

from ..utils.models import Mutable
from .base import EntityId


class EngineAggregate[ActorState: BaseModel, ItemState: BaseModel](Mutable):
    """An engine's id-keyed side table; the commit validator keeps its keys tracking the world."""

    actors: dict[EntityId, ActorState] = Field(default_factory=dict)
    items: dict[EntityId, ItemState] = Field(default_factory=dict)

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
