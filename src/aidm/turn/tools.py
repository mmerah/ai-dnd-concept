from collections.abc import Callable, Mapping

from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, FunctionToolset, WrapperToolset

from aidm.engines import sheets
from aidm.engines.engine import Engine, PlanContext
from aidm.engines.transact import act, sequential_toolset
from aidm.state import actions
from aidm.state.base import PLAYER_ID, EntityId, Slug
from aidm.state.facts import Fact
from aidm.state.world import AdvanceThread, Game


def core_toolset() -> FunctionToolset[PlanContext]:
    def reveal(ctx: RunContext[PlanContext], entity_id: EntityId) -> str:
        """Reveal an entity that exists but the player does not know yet: they notice it, are told
        of it, or reach it.

        Args:
            entity_id: Exact id of the unrevealed canon entity.
        """
        return _resolved(ctx, lambda draft: actions.reveal(draft, entity_id))

    def move(ctx: RunContext[PlanContext], entity_id: EntityId, to_id: EntityId) -> str:
        """Move an actor who actually changes location, or one item within the player's reach:
        picked up, set down here, or handed to an actor here.

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
        canon entry of its own.

        Args:
            item_name: The object written out, such as 'a handful of gravel'.
        """
        return _resolved(ctx, lambda draft: actions.improvise(draft, item_name))

    def add_trait(
        ctx: RunContext[PlanContext], entity_id: EntityId, trait_id: Slug, text: str
    ) -> str:
        """Put a lasting condition, skill, or frailty on an entity.

        Args:
            entity_id: Exact id of the entity affected; an actor must be here with the player.
            trait_id: Stable slug for the trait, such as `poisoned`; it shows written out, so
                `battle-worn` appears as Battle Worn.
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

    def advance_thread(ctx: RunContext[PlanContext], advance: AdvanceThread) -> str:
        """Move a storyline the scenario is tracking: where it stands now, or that it is over.

        Args:
            advance: The movement to apply.
        """
        return _resolved(ctx, lambda draft: actions.advance_thread(draft, advance))

    def unlock_exit(ctx: RunContext[PlanContext], to_id: EntityId) -> str:
        """Open a locked way out of the player's location.

        Args:
            to_id: Exact id of the location the way leads to.
        """
        return _resolved(ctx, lambda draft: actions.unlock_exit(draft, to_id))

    def join_party(ctx: RunContext[PlanContext], actor_id: EntityId) -> str:
        """Put an actor into the player's party.

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

    def complete_chapter(ctx: RunContext[PlanContext]) -> str:
        """Record that the chapter of the story this character has been living has closed."""
        ending = ctx.deps.engine.chapter_ending
        return _resolved(ctx, lambda draft: sheets.complete_chapter(draft, ending))

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
            complete_chapter,
        ]
    )


def offered_tools(engine: Engine[sheets.SheetBase]) -> tuple[ToolDefinition, ...]:
    """Every tool the Director may be handed this game, unfiltered: the vocabulary a turn is
    planned in, so a renamed tool cannot drift out of the role that plans it."""
    return tuple(
        tool.tool_def
        for toolset in (core_toolset(), *engine.director_toolsets)
        for tool in _declared(toolset).tools.values()
    )


def vocabulary(engine: Engine[sheets.SheetBase]) -> str:
    return "\n".join(
        f"- `{tool.name}` — {' '.join((tool.description or '').split())}"
        for tool in offered_tools(engine)
    )


def _declared(toolset: AbstractToolset[PlanContext]) -> FunctionToolset[PlanContext]:
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
    if not isinstance(toolset, FunctionToolset):
        raise TypeError(f"{type(toolset).__name__} declares no tools to plan from")
    return toolset


def _resolved(ctx: RunContext[PlanContext], apply: Callable[[Game], list[Fact]]) -> str:
    return act(ctx, lambda draft, _rng: tuple(apply(draft)))


def _a_locked_way_out(state: Game) -> bool:
    here = state.world.require_kind(state.player_location, "location")
    return any(way.locked for way in here.exits)


def _an_actor_to_recruit(state: Game) -> bool:
    return any(
        entity.kind == "actor" and entity.id != PLAYER_ID and entity.id not in state.world.party
        for entity in state.world.entities
        if state.is_here(entity)
    )


def _a_party_member(state: Game) -> bool:
    return bool(state.world.party)


def _an_unresolved_thread(state: Game) -> bool:
    # The set the scene renders under ACTIVE THREADS: a thread put dormant is still movable.
    return any(thread.status != "resolved" for thread in state.world.threads)


def _a_trait_in_reach(state: Game) -> bool:
    # `is_here` is false of a location, which carries tags of its own that `add_trait` may write.
    return any(
        entity.traits
        for entity in state.world.entities
        if state.is_here(entity) or entity.id == state.player_location
    )


_APPLIES: Mapping[str, Callable[[Game], bool]] = {
    "unlock_exit": _a_locked_way_out,
    "join_party": _an_actor_to_recruit,
    "leave_party": _a_party_member,
    "advance_thread": _an_unresolved_thread,
    "remove_trait": _a_trait_in_reach,
}


def possible(name: str, state: Game) -> bool:
    applies = _APPLIES.get(name)
    return applies is None or applies(state)
