from random import Random

from aidm.domain.entities import Entity
from aidm.domain.events import (
    ActorMoved,
    EntityCreated,
    EntityDiscovered,
    Event,
    ItemMoved,
    RuleEvent,
)
from aidm.domain.state import GameState

from .constants import ENGINE_ID, SCHEMA_VERSION
from .domain.models.direction import Dnd5eDirection
from .domain.models.events import Dnd5eEvent
from .domain.reducer import apply_rule
from .engine.resolve import resolve as resolve_mechanics
from .engine.ruleset import Ruleset
from .events import decode_dnd5e_event, encode_dnd5e_event
from .models import Dnd5eState
from .state import created_state, dnd5e_state


class Dnd5eRules:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def resolve(
        self,
        direction: Dnd5eDirection,
        state: GameState,
        rng: Random,
    ) -> list[Event]:
        events = resolve_mechanics(direction.mechanics, state, rng, self._ruleset)
        return [_as_core_event(event) for event in events]

    @staticmethod
    def created(state: GameState, entity: Entity) -> Dnd5eState:
        return created_state(state, entity)

    def apply(self, state: GameState, event: RuleEvent) -> Dnd5eState:
        return apply_rule(state, decode_dnd5e_event(event, ENGINE_ID, SCHEMA_VERSION))

    def validate_state(self, state: GameState) -> None:
        engine = dnd5e_state(state)
        for actor_id, actor in engine.actors.items():
            if actor.ref is not None and not self._ruleset.provides(actor.ref):
                raise ValueError(f"5e actor {actor_id!r} has unknown ref {actor.ref}")
        for item_id, item in engine.items.items():
            if item.ref is not None and not self._ruleset.provides(item.ref):
                raise ValueError(f"5e item {item_id!r} has unknown ref {item.ref}")


def _as_core_event(event: Dnd5eEvent) -> Event:
    """Topology events are already core's; mechanics events travel in a rule envelope."""
    match event:
        case EntityCreated() | EntityDiscovered() | ActorMoved() | ItemMoved():
            return event
        case _:
            return encode_dnd5e_event(event, ENGINE_ID, SCHEMA_VERSION)
