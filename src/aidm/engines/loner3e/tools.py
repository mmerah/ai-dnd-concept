from collections.abc import Callable

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.engines.engine import PlanContext
from aidm.engines.transact import act, sequential_toolset
from aidm.state.base import EntityId
from aidm.state.resolution import Resolution
from aidm.state.world import GameState

from .actions import Position, Question, apply_end_adventure, apply_restore_luck, resolve_question

type Twists = Callable[[GameState], tuple[tuple[str, str], ...]]


def director_toolset(twists: Twists) -> FunctionToolset[PlanContext]:
    def roll_question(
        ctx: RunContext[PlanContext],
        actor_id: EntityId,
        question: str,
        position: Position = "neutral",
        edge: str = "",
        opponent_id: EntityId | None = None,
    ) -> str:
        """Put a closed dramatic question to Chance d6 against Risk d6. Ask one when the answer is
        uncertain and both a yes and a no would change the fiction. Never state the answer
        yourself: what comes back is what the dice settled.

        Args:
            actor_id: Exact id of the actor the question is about: the player, or an actor here.
            question: The closed dramatic question the dice answer, phrased so that yes is what
                the actor wants.
            position: Your judgment of the fiction: `advantage` when a skill, gear, trait or the
                situation gives the actor a real edge here; `disadvantage` when a frailty, an
                opposing tag or the situation works against them; `neutral` when neither clearly
                outweighs.
            edge: The tag or circumstance that decided the position, in a few words. Empty for
                neutral.
            opponent_id: Exact id of the actor opposing this, set only when the question is one
                exchange of a conflict; the engine then takes luck off whichever side loses it.
        """
        return act(
            ctx,
            lambda draft, rng: resolve_question(
                draft,
                Question(
                    actor_id=actor_id,
                    question=question,
                    position=position,
                    edge=edge,
                    opponent_id=opponent_id,
                ),
                rng,
                twists(draft),
            ),
        )

    def restore_luck(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor's luck back to full, once a conflict is behind them and they have had a
        breather. The engine already refills both sides when a conflict ends at 0.

        Args:
            actor_id: Exact id of the actor: the player, or an actor here.
        """
        return act(
            ctx,
            lambda draft, _rng: Resolution(facts=tuple(apply_restore_luck(draft, actor_id))),
        )

    def end_adventure(ctx: RunContext[PlanContext]) -> str:
        """Record that the adventure has ended — the fiction's own boundary, called once when the
        story genuinely closes, usually alongside resolving its thread. Never for a mere scene
        ending."""
        return act(ctx, lambda draft, _rng: Resolution(facts=tuple(apply_end_adventure(draft))))

    return sequential_toolset([roll_question, restore_luck, end_adventure])
