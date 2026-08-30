from pathlib import Path
from typing import Literal

from pydantic import Field

from aidm.content.io import engine_text
from aidm.state.entities import CheckedEntityId, Frozen, Slug
from aidm.state.facts import Fact
from aidm.state.model import AdvanceThread, Game
from aidm.state.tools import DirectorTool, advance_thread, director_tool
from aidm.world import actions

# The prompt fragment that names these tools; a non-rooms engine ships neither.
DIRECTOR_WORLD = engine_text(Path(__file__).parent / "prompts" / "director_world.md")


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of the hidden entity.")


class Move(Frozen):
    """Move an actor to a new location, or move a nearby item."""

    verb: Literal["move"]
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
    """Give the player an ordinary, unimportant object not already in the world."""

    verb: Literal["gain_improvised_item"]
    item_name: str = Field(description="The object's name, such as `a handful of gravel`.")


class AddTrait(Frozen):
    """Add a lasting condition or quality to an entity."""

    verb: Literal["add_trait"]
    entity_id: CheckedEntityId = Field(
        description="Exact entity id. An actor must be here with the player."
    )
    name: str = Field(
        min_length=1,
        description="The trait's display name, such as `Battle Worn`; its id is derived.",
    )
    text: str = Field(description="The trait's effect in plain language.")


class RemoveTrait(Frozen):
    """Remove a lasting condition or quality that has ended."""

    verb: Literal["remove_trait"]
    entity_id: CheckedEntityId = Field(
        description="Exact entity id. An actor must be here with the player."
    )
    trait_id: Slug = Field(description="Exact id of one of the entity's traits.")


class Kill(Frozen):
    """Record that an actor has died. Their body and what they carried stay in the world."""

    verb: Literal["kill"]
    actor_id: CheckedEntityId = Field(
        description="Exact id of the actor who has died. They must be here with the player."
    )


class UnlockExit(Frozen):
    """Unlock an exit from the player's location."""

    verb: Literal["unlock_exit"]
    to_id: CheckedEntityId = Field(description="Exact id of the exit's destination.")


class JoinParty(Frozen):
    """Add an actor here to the player's party."""

    verb: Literal["join_party"]
    actor_id: CheckedEntityId = Field(description="Exact id of the actor joining.")


class LeaveParty(Frozen):
    """Remove an actor from the player's party."""

    verb: Literal["leave_party"]
    actor_id: CheckedEntityId = Field(description="Exact id of the actor leaving.")


class AdvanceThreadArm(AdvanceThread):
    """Update an active storyline's status or note."""

    verb: Literal["advance_thread"]


# A plain alias, not `type`: the union must flatten so the discriminator sees every arm.
WorldChange = (
    GainImprovisedItem
    | Reveal
    | Move
    | AddTrait
    | RemoveTrait
    | Kill
    | UnlockExit
    | JoinParty
    | LeaveParty
    | AdvanceThreadArm
)

_CHANGE_DESCRIPTION = "The one world change to apply; `verb` picks the change."


class ChangeWorld(Frozen):
    change: WorldChange = Field(discriminator="verb", description=_CHANGE_DESCRIPTION)


def apply_change(draft: Game, change: WorldChange) -> list[Fact]:
    match change:
        case Reveal():
            return actions.reveal(draft, change.entity_id)
        case Move():
            return actions.move(draft, change.entity_id, change.to_id)
        case GainImprovisedItem():
            return actions.improvise(draft, change.item_name)
        case AddTrait():
            return actions.add_trait(draft, change.entity_id, change.name, change.text)
        case RemoveTrait():
            return actions.remove_trait(draft, change.entity_id, change.trait_id)
        case Kill():
            return actions.kill(draft, change.actor_id)
        case UnlockExit():
            return actions.unlock_exit(draft, change.to_id)
        case JoinParty():
            return actions.join_party(draft, change.actor_id)
        case LeaveParty():
            return actions.leave_party(draft, change.actor_id)
        case AdvanceThreadArm():
            return advance_thread(draft, change)


def rooms_tools(*extra: DirectorTool) -> tuple[DirectorTool, ...]:
    change_world = director_tool(
        "change_world",
        "Apply one settled world change to match the story. Set `verb` to pick the change and "
        "fill that verb's own fields. One call makes one change.",
        ChangeWorld,
        lambda draft, one, _rng: apply_change(draft, one.change),
        during_suspension=True,
    )
    return (change_world, *extra)
