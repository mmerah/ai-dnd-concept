from random import Random

from aidm.base import PLAYER_ID
from aidm.transition import Transition
from aidm.world import GameState

from .access import dnd5e_actor, dnd5e_item
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

    def validate_state(self, state: GameState) -> None:
        actors = tuple(dnd5e_actor(record) for record in state.world.actors.values())
        for actor in actors:
            if actor.ref is not None and not self._ruleset.provides(actor.ref):
                raise ValueError(f"5e actor {actor.id!r} has unknown ref {actor.ref}")
        for record in state.world.items.values():
            item = dnd5e_item(record)
            if item.ref is not None and not self._ruleset.provides(item.ref):
                raise ValueError(f"5e item {item.id!r} has unknown ref {item.ref}")
        # `LeveledUp` names no target, so an NPC carrying progression would be ambiguous.
        levelled = sorted(
            actor.id for actor in actors if actor.progression is not None and actor.id != PLAYER_ID
        )
        if levelled:
            raise ValueError(f"only the player may have progression: {levelled}")
