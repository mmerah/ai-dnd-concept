from dataclasses import dataclass
from random import Random

from aidm.base import EntityId
from aidm.world import GameState

from ..access import Dnd5eWorld
from ..ruleset import Ruleset
from ..state import Dnd5eActor, Progression


@dataclass(frozen=True, slots=True)
class Resolution:
    """The draft a turn's mechanics mutate, with the dice and rules they read."""

    world: Dnd5eWorld
    rng: Random
    ruleset: Ruleset

    @property
    def draft(self) -> GameState:
        return self.world.state

    @property
    def player(self) -> Dnd5eActor:
        return self.world.player()

    @property
    def progression(self) -> Progression:
        progression = self.player.progression
        if progression is None:
            raise ValueError("the player has no class")
        return progression

    def actor(self, entity_id: EntityId) -> Dnd5eActor:
        return self.world.actor(entity_id)

    def actor_here(self, entity_id: EntityId) -> Dnd5eActor:
        """Reject off-screen actors because this turn cannot visibly affect them."""
        actor = self.actor(entity_id)
        if actor.entity.parent_id != self.player.entity.parent_id:
            raise ValueError(f"cannot affect {entity_id!r}: not at the player's location")
        return actor

    def target(self, entity_id: EntityId | None) -> Dnd5eActor:
        """Default to the player because roles never see the player ID."""
        return self.player if entity_id is None else self.actor_here(entity_id)
