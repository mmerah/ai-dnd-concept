from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.engines.engine import PlanContext
from aidm.engines.transact import act, sequential_toolset
from aidm.state.base import EntityId
from aidm.state.resolution import Resolution

from .actions import (
    Attempt,
    LuckTest,
    apply_change_credits,
    apply_complete_job,
    resolve_attempt,
    resolve_luck_test,
)


def director_toolset() -> FunctionToolset[PlanContext]:
    def roll_attempt(
        ctx: RunContext[PlanContext],
        actor_id: EntityId,
        goal: str,
        skill: str = "",
        helped: str = "",
        helper_id: EntityId | None = None,
        helper_skill: str = "",
        hindered: str = "",
        luck_test: str = "",
    ) -> str:
        """Put one risky attempt to the highest die of a pool. Call for one only when failing would
        cost something real. Never state the outcome yourself: what comes back is what the dice
        settled.

        Args:
            actor_id: Exact id of the actor attempting this: the player, or an actor here.
            goal: What the actor is trying to do and what they risk by trying, in one line.
            skill: The skill on the actor's sheet this calls on, copied exactly as it is written
                there. Empty when none of theirs applies: they roll the bare d6.
            helped: The circumstance that makes this easier — a skill, a piece of gear, the ground
                they hold, an ally's presence — in a few words. Empty when nothing does, and never
                alongside `helper_id`.
            helper_id: Exact id of an ally here who helps with this — they roll their own skill die
                into the pool. Null when nobody helps.
            helper_skill: The skill on the *helper's* sheet this calls on, copied exactly as it is
                written there. Empty when none of theirs applies: they roll the bare d6.
            hindered: The circumstance that makes this harder, in a few words. Empty when nothing
                does.
            luck_test: What bad luck might arrive alongside this — running out of ammo, running
                into guards. The engine rolls whether it does. Empty for no test.
        """
        return act(
            ctx,
            lambda draft, rng: resolve_attempt(
                draft,
                Attempt(
                    actor_id=actor_id,
                    goal=goal,
                    skill=skill,
                    helped=helped,
                    helper_id=helper_id,
                    helper_skill=helper_skill,
                    hindered=hindered,
                    luck_test=luck_test,
                ),
                rng,
            ),
        )

    def roll_luck_test(ctx: RunContext[PlanContext], actor_id: EntityId, subject: str) -> str:
        """Put the SRD's standalone bad-luck test to the dice, for a turn where nothing is
        attempted but bad luck might still arrive.

        Args:
            actor_id: Exact id of the actor whose luck is tested: the player, or an actor here.
            subject: What bad luck might arrive — running out of ammo, running into guards. The
                engine rolls whether it does.
        """
        return act(
            ctx,
            lambda draft, rng: resolve_luck_test(
                draft, LuckTest(actor_id=actor_id, subject=subject), rng
            ),
        )

    def change_credits(ctx: RunContext[PlanContext], actor_id: EntityId, amount: int) -> str:
        """Move an actor's credits for gear bought, repairs paid, debts collected or pay earned —
        never for a roll's own outcome, which the engine settles itself.

        Args:
            actor_id: Exact id of the actor: the player, or an actor here.
            amount: Positive to pay them, negative to charge them. A charge the pool cannot cover
                is refused.
        """
        return act(
            ctx,
            lambda draft, _rng: Resolution(
                facts=tuple(apply_change_credits(draft, actor_id, amount))
            ),
        )

    def complete_job(ctx: RunContext[PlanContext]) -> str:
        """Record that the job is done — the fiction's own boundary, called once when the crew's
        engagement genuinely closes, usually alongside resolving its thread. Never for a mere scene
        ending."""
        return act(ctx, lambda draft, _rng: Resolution(facts=tuple(apply_complete_job(draft))))

    return sequential_toolset([roll_attempt, roll_luck_test, change_credits, complete_job])
