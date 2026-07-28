"""The context every mechanic resolves against."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from random import Random
from typing import Self

from ...content import Library
from ...domain.models import ActorEntity, Entity, EntityId, Event, GameState, ItemEntity
from ...domain.reducer import apply


@dataclass(frozen=True, slots=True)
class Resolution:
    """Everything a mechanic reads, so no slice threads `(state, rng, library)` by hand.

    The lookups are turn policy rather than entity lookup — "the player must have witnessed it"
    — which is why they live here beside the rng and not on `WorldState`."""

    state: GameState
    rng: Random
    library: Library

    def then(self, events: Sequence[Event]) -> Self:
        """The same context over the world those events produced."""
        return replace(self, state=apply(self.state, events))

    @property
    def player(self) -> ActorEntity:
        return self.state.player

    def entity(self, entity_id: EntityId) -> Entity:
        return self.state.world.require(entity_id)

    def of_kind[T: Entity](self, entity_id: EntityId, expected: type[T]) -> T:
        return self.state.world.require_kind(entity_id, expected)

    def actor_here(self, entity_id: EntityId) -> ActorEntity:
        """An actor the player is standing with; anyone else is off-screen, and what the player
        never witnessed must not reach the Narrator."""
        actor = self.of_kind(entity_id, ActorEntity)
        if actor.location_id != self.player.location_id:
            raise ValueError(f"cannot affect {entity_id!r}: not at the player's location")
        return actor

    def target(self, entity_id: EntityId | None) -> ActorEntity:
        """An omitted actor id is the player throughout the vocabulary — they are the one actor no
        role is shown an id for."""
        return self.player if entity_id is None else self.actor_here(entity_id)

    def held(self, entity_id: EntityId, verb: str) -> ItemEntity:
        item = self.of_kind(entity_id, ItemEntity)
        if item.container_id != self.player.id:
            raise ValueError(f"cannot {verb} {entity_id!r}: the player is not carrying it")
        return item
