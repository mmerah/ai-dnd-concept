from random import Random

from pydantic import ValidationError

from aidm.base import PLAYER_ID
from aidm.transition import Direction, Transition
from aidm.world import GameState

from .access import Dnd5eWorld
from .direction import load_mechanics
from .resolve import resolve as resolve_mechanics
from .ruleset import Ruleset


class Dnd5eProposalRejected(ValueError):
    pass


class Dnd5eRules:
    def __init__(self, ruleset: Ruleset) -> None:
        self._ruleset = ruleset

    def resolve(self, direction: Direction, state: GameState, rng: Random) -> Transition:
        mechanics = load_mechanics(direction)
        world = Dnd5eWorld(state=state.draft())
        try:
            facts = resolve_mechanics(mechanics, world, rng, self._ruleset)
        except ValidationError:
            raise
        except ValueError as error:
            raise Dnd5eProposalRejected(str(error)) from error
        return Transition(state=world.commit(), facts=tuple(facts))

    def validate_state(self, state: GameState) -> None:
        world = Dnd5eWorld(state=state)
        actors = world.actors()
        for actor in actors:
            if actor.ref is not None and not self._ruleset.provides(actor.ref):
                raise ValueError(f"5e actor {actor.id!r} has unknown ref {actor.ref}")
        for item in world.items():
            if item.ref is not None and not self._ruleset.provides(item.ref):
                raise ValueError(f"5e item {item.id!r} has unknown ref {item.ref}")
        # `LeveledUp` names no target, so an NPC carrying progression would be ambiguous.
        levelled = sorted(
            actor.id for actor in actors if actor.progression is not None and actor.id != PLAYER_ID
        )
        if levelled:
            raise ValueError(f"only the player may have progression: {levelled}")
