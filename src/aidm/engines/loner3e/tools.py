from collections.abc import Callable

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.engines.engine import PlanContext
from aidm.engines.transact import act, sequential_toolset
from aidm.state.base import EntityId
from aidm.state.resolution import Resolution
from aidm.state.world import Game

from .actions import Question, apply_end_adventure, apply_restore_luck, resolve_question

type Twists = Callable[[Game], tuple[tuple[str, str], ...]]


def director_toolset(twists: Twists) -> FunctionToolset[PlanContext]:
    def roll_question(ctx: RunContext[PlanContext], question: Question) -> str:
        """Put a closed dramatic question to Chance d6 against Risk d6.

        Args:
            question: The question to put to the dice.
        """
        return act(ctx, lambda draft, rng: resolve_question(draft, question, rng, twists(draft)))

    def restore_luck(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor's luck back to full.

        Args:
            actor_id: Exact id of the actor: the player, or an actor here.
        """
        return act(
            ctx,
            lambda draft, _rng: Resolution(facts=tuple(apply_restore_luck(draft, actor_id))),
        )

    def end_adventure(ctx: RunContext[PlanContext]) -> str:
        """Record that the adventure has ended."""
        return act(ctx, lambda draft, _rng: Resolution(facts=tuple(apply_end_adventure(draft))))

    return sequential_toolset([roll_question, restore_luck, end_adventure])
