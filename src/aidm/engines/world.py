from collections.abc import Callable, Sequence

from pydantic import BaseModel, Field

from aidm.engines.core import Command, Engine, action
from aidm.state import actions
from aidm.state.entities import CheckedEntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.model import AdvanceThread, Game


def _world_command[A: BaseModel](
    name: str, description: str, args: type[A], act: Callable[[Game, A], Sequence[Fact]]
) -> Command:
    """Carried by every core command here, so a new one cannot forget the suspension rule."""
    return action(name, description, args, act, during_suspension=True)


class Reveal(Frozen):
    entity_id: CheckedEntityId = Field(description="Exact id of the hidden entity.")


class Move(Frozen):
    entity_id: CheckedEntityId = Field(
        description="Exact actor or item id. The item must be carried by the player or loose here."
    )
    to_id: CheckedEntityId = Field(
        description=(
            "Exact destination id. An actor moves to a location id. An item is taken by moving "
            "it to `player`, handed over by moving it to an actor here, and dropped by moving it "
            "to the id of the player's current location."
        )
    )


class GainImprovisedItem(Frozen):
    item_name: str = Field(description="The object's name, such as `a handful of gravel`.")


class AddTrait(Frozen):
    entity_id: CheckedEntityId = Field(
        description="Exact entity id. An actor must be here with the player."
    )
    name: str = Field(
        min_length=1,
        description="The trait's display name, such as `Battle Worn`; its id is derived.",
    )
    text: str = Field(description="The trait's effect in plain language.")


class RemoveTrait(Frozen):
    entity_id: CheckedEntityId = Field(
        description="Exact entity id. An actor must be here with the player."
    )
    trait_id: Slug = Field(description="Exact id of one of the entity's traits.")


class Kill(Frozen):
    actor_id: CheckedEntityId = Field(
        description="Exact id of the actor who has died. They must be here with the player."
    )


class UnlockExit(Frozen):
    to_id: CheckedEntityId = Field(description="Exact id of the exit's destination.")


class JoinParty(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor joining.")


class LeaveParty(Frozen):
    actor_id: CheckedEntityId = Field(description="Exact id of the actor leaving.")


CORE_COMMANDS: tuple[Command, ...] = (
    _world_command(
        "reveal",
        "Make a hidden entity known when the player notices, finds, or reaches it.",
        Reveal,
        lambda draft, one: actions.reveal(draft, one.entity_id),
    ),
    _world_command(
        "move",
        "Move an actor to a new location, or move a nearby item.",
        Move,
        lambda draft, one: actions.move(draft, one.entity_id, one.to_id),
    ),
    _world_command(
        "gain_improvised_item",
        "Give the player an ordinary, unimportant object not already in the world.",
        GainImprovisedItem,
        lambda draft, one: actions.improvise(draft, one.item_name),
    ),
    _world_command(
        "add_trait",
        "Add a lasting condition or quality to an entity.",
        AddTrait,
        lambda draft, one: actions.add_trait(draft, one.entity_id, one.name, one.text),
    ),
    _world_command(
        "remove_trait",
        "Remove a lasting condition or quality that has ended.",
        RemoveTrait,
        lambda draft, one: actions.remove_trait(draft, one.entity_id, one.trait_id),
    ),
    _world_command(
        "kill",
        "Record that an actor has died. Their body and what they carried stay in the world.",
        Kill,
        lambda draft, one: actions.kill(draft, one.actor_id),
    ),
    _world_command(
        "advance_thread",
        "Update an active storyline's status, stage, clock, or note.",
        AdvanceThread,
        actions.advance_thread,
    ),
    _world_command(
        "unlock_exit",
        "Unlock an exit from the player's location.",
        UnlockExit,
        lambda draft, one: actions.unlock_exit(draft, one.to_id),
    ),
    _world_command(
        "join_party",
        "Add an actor here to the player's party.",
        JoinParty,
        lambda draft, one: actions.join_party(draft, one.actor_id),
    ),
    _world_command(
        "leave_party",
        "Remove an actor from the player's party.",
        LeaveParty,
        lambda draft, one: actions.leave_party(draft, one.actor_id),
    ),
)


def commands(engine: Engine) -> tuple[Command, ...]:
    """The shared world vocabulary always comes first; an engine only adds its own mechanics."""
    return (*CORE_COMMANDS, *engine.director_commands)
