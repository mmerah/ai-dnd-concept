from collections.abc import Callable

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.engines.engine import PlanContext
from aidm.engines.transact import act, sequential_toolset
from aidm.state import actions
from aidm.state.base import EntityId, Slug, ThreadStatus
from aidm.state.facts import Fact
from aidm.state.resolution import Resolution
from aidm.state.world import AdvanceThread, GameState


def core_toolset() -> FunctionToolset[PlanContext]:
    def reveal(ctx: RunContext[PlanContext], entity_id: EntityId) -> str:
        """Reveal an entity that exists but the player does not know yet: they notice it, are told
        of it, or reach it. Prefer this over inventing a replacement.

        Args:
            entity_id: Exact id of the unrevealed canon entity.
        """
        return _resolved(ctx, lambda draft: actions.reveal(draft, entity_id))

    def move(ctx: RunContext[PlanContext], entity_id: EntityId, to_id: EntityId) -> str:
        """Move an actor who actually changes location, or one item within the player's reach:
        picked up, set down here, or handed to an actor here. Moving the player to an unrevealed
        location reveals it.

        Args:
            entity_id: Exact id of the actor or item that moves; `player` is the played character.
                An item must be one the player carries, or one loose at their location.
            to_id: Exact id of where it goes: for an actor the location they enter; for an item,
                `player` to pick it up, an actor here with the player to hand it over, or the
                player's own location to set it down.
        """
        return _resolved(ctx, lambda draft: actions.move(draft, entity_id, to_id))

    def gain_improvised_item(ctx: RunContext[PlanContext], item_name: str) -> str:
        """Give the player an ordinary incidental object that is not in canon and is not worth a
        canon entry of its own. Never a substitute for an item that already exists.

        Args:
            item_name: The object written out, such as 'a handful of gravel'.
        """
        return _resolved(ctx, lambda draft: actions.improvise(draft, item_name))

    def add_trait(
        ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug, text: str
    ) -> str:
        """Put a lasting condition, skill, or frailty on an entity. The trait shows the id written
        out: `battle-worn` appears as Battle Worn.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Stable slug for the trait, such as `poisoned`.
            text: The constraint or benefit it puts on the entity, in prose.
        """
        return _resolved(ctx, lambda draft: actions.add_trait(draft, entity_id, trait_id, text))

    def remove_trait(ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug) -> str:
        """Lift a lasting condition, skill, or frailty the fiction has ended.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Exact id of a trait the entity carries.
        """
        return _resolved(ctx, lambda draft: actions.remove_trait(draft, entity_id, trait_id))

    def advance_thread(
        ctx: RunContext[PlanContext],
        thread_id: Slug,
        status: ThreadStatus | None = None,
        stage: Slug | None = None,
        tick: int = 0,
    ) -> str:
        """Move a storyline the scenario is tracking: where it stands now, or that it is over.

        Args:
            thread_id: Exact id of one thread in ACTIVE THREADS.
            status: Where the thread now stands, or null to leave it as it is.
            stage: Stable slug for the point it has reached, or null to leave it as it is.
            tick: How many segments this fills on the thread's clock, when it has one.
        """
        return _resolved(
            ctx,
            # Built inside the play, so the model's own retry carries what the fields refuse.
            lambda draft: actions.advance_thread(
                draft, AdvanceThread(thread_id=thread_id, status=status, stage=stage, tick=tick)
            ),
        )

    def unlock_exit(ctx: RunContext[PlanContext], location_id: EntityId, to_id: EntityId) -> str:
        """Open a locked way when the fiction opens it — a key turned, a bar lifted, a seal broken.

        Args:
            location_id: Exact id of the location the way leads from.
            to_id: Exact id of the location it leads to.
        """
        return _resolved(ctx, lambda draft: actions.unlock_exit(draft, location_id, to_id))

    def join_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor here with the player into their party; a party member travels with them.

        Args:
            actor_id: Exact id of the actor joining, who must be here with the player.
        """
        return _resolved(ctx, lambda draft: actions.join_party(draft, actor_id))

    def leave_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Take an actor out of the player's party when the fiction parts them.

        Args:
            actor_id: Exact id of the actor leaving.
        """
        return _resolved(ctx, lambda draft: actions.leave_party(draft, actor_id))

    return sequential_toolset(
        [
            reveal,
            move,
            gain_improvised_item,
            add_trait,
            remove_trait,
            advance_thread,
            unlock_exit,
            join_party,
            leave_party,
        ]
    )


def _resolved(ctx: RunContext[PlanContext], apply: Callable[[GameState], list[Fact]]) -> str:
    return act(ctx, lambda draft, _rng: Resolution(facts=tuple(apply(draft))))
