from collections.abc import Callable

from pydantic import BaseModel, Field

from aidm.engines.core import Command, DirectorContext, Engine, apply_action, command
from aidm.state import actions
from aidm.state.entities import CheckedEntityId, Frozen, Slug
from aidm.state.model import AdvanceThread


def _world_command[A: BaseModel](
    name: str, description: str, args: type[A], run: Callable[[DirectorContext, A], str]
) -> Command:
    """Carried by every core command here, so a new one cannot forget the suspension rule."""
    return command(name, description, args, run, during_suspension=True)


class Reveal(Frozen):
    entity_id: CheckedEntityId = Field(description="Exact id of the hidden entity.")


def _reveal(deps: DirectorContext, args: Reveal) -> str:
    return apply_action(deps, lambda draft: actions.reveal(draft, args.entity_id))


class Move(Frozen):
    entity_id: CheckedEntityId = Field(
        description="Exact actor or item id. The item must be carried by the player or loose here."
    )
    to_id: CheckedEntityId = Field(
        description=(
            "Exact destination id. Use a location for an actor; for an item, use `player`,\n"
            "an actor here, or the player's location."
        )
    )


def _move(deps: DirectorContext, args: Move) -> str:
    return apply_action(deps, lambda draft: actions.move(draft, args.entity_id, args.to_id))


class GainImprovisedItem(Frozen):
    item_name: str = Field(description="The object's name, such as `a handful of gravel`.")


def _gain_improvised_item(deps: DirectorContext, args: GainImprovisedItem) -> str:
    return apply_action(deps, lambda draft: actions.improvise(draft, args.item_name))


class AddTrait(Frozen):
    entity_id: CheckedEntityId = Field(
        description="Exact entity id. An actor must be here with the player."
    )
    trait_id: Slug = Field(
        description="Stable slug, such as `poisoned`. `battle-worn` displays as Battle Worn."
    )
    text: str = Field(description="The trait's effect in plain language.")


def _add_trait(deps: DirectorContext, args: AddTrait) -> str:
    return apply_action(
        deps, lambda draft: actions.add_trait(draft, args.entity_id, args.trait_id, args.text)
    )


class RemoveTrait(Frozen):
    entity_id: CheckedEntityId = Field(
        description="Exact entity id. An actor must be here with the player."
    )
    trait_id: Slug = Field(description="Exact id of one of the entity's traits.")


def _remove_trait(deps: DirectorContext, args: RemoveTrait) -> str:
    return apply_action(
        deps, lambda draft: actions.remove_trait(draft, args.entity_id, args.trait_id)
    )


def _advance_thread(deps: DirectorContext, args: AdvanceThread) -> str:
    return apply_action(deps, lambda draft: actions.advance_thread(draft, args))


class UnlockExit(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the exit's destination.")


def _unlock_exit(deps: DirectorContext, args: UnlockExit) -> str:
    return apply_action(deps, lambda draft: actions.unlock_exit(draft, args.to_id))


class JoinParty(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor joining.")


def _join_party(deps: DirectorContext, args: JoinParty) -> str:
    return apply_action(deps, lambda draft: actions.join_party(draft, args.actor_id))


class LeaveParty(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor leaving.")


def _leave_party(deps: DirectorContext, args: LeaveParty) -> str:
    return apply_action(deps, lambda draft: actions.leave_party(draft, args.actor_id))


CORE_COMMANDS: tuple[Command, ...] = (
    _world_command(
        "reveal",
        "Make a hidden entity known when the player notices, finds, or reaches it.",
        Reveal,
        _reveal,
    ),
    _world_command("move", "Move an actor to a new location, or move a nearby item.", Move, _move),
    _world_command(
        "gain_improvised_item",
        "Give the player an ordinary, unimportant object not already in the world.",
        GainImprovisedItem,
        _gain_improvised_item,
    ),
    _world_command(
        "add_trait", "Add a lasting condition or quality to an entity.", AddTrait, _add_trait
    ),
    _world_command(
        "remove_trait",
        "Remove a lasting condition or quality that has ended.",
        RemoveTrait,
        _remove_trait,
    ),
    _world_command(
        "advance_thread",
        "Update an active storyline's status, stage, clock, or note.",
        AdvanceThread,
        _advance_thread,
    ),
    _world_command(
        "unlock_exit", "Unlock an exit from the player's location.", UnlockExit, _unlock_exit
    ),
    _world_command(
        "join_party", "Add an actor here to the player's party.", JoinParty, _join_party
    ),
    _world_command(
        "leave_party", "Remove an actor from the player's party.", LeaveParty, _leave_party
    ),
)


def commands(engine: Engine) -> tuple[Command, ...]:
    """The shared world vocabulary always comes first; an engine only adds its own mechanics."""
    return (*CORE_COMMANDS, *engine.director_commands)
