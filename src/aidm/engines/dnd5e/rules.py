from random import Random

from aidm.base import Entity
from aidm.transition import Transition
from aidm.world import GameState

from .access import created_state, dnd5e_state
from .direction import Dnd5eDirection
from .resolve import resolve as resolve_mechanics
from .ruleset import Ruleset


class Dnd5eRules:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def resolve(self, direction: Dnd5eDirection, state: GameState, rng: Random) -> Transition:
        draft = state.draft()
        facts = resolve_mechanics(direction.mechanics, draft, rng, self._ruleset)
        return Transition(state=draft.committed(), facts=tuple(facts))

    @staticmethod
    def created(draft: GameState, entity: Entity) -> None:
        created_state(draft, entity)

    def validate_state(self, state: GameState) -> None:
        engine = dnd5e_state(state)
        for actor_id, actor in engine.actors.items():
            if actor.ref is not None and not self._ruleset.provides(actor.ref):
                raise ValueError(f"5e actor {actor_id!r} has unknown ref {actor.ref}")
        for item_id, item in engine.items.items():
            if item.ref is not None and not self._ruleset.provides(item.ref):
                raise ValueError(f"5e item {item_id!r} has unknown ref {item.ref}")
