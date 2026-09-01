from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from aidm.core.entities import DEAD, CheckedEntityId, EntityId, Frozen, Trait
from aidm.core.facts import Fact
from aidm.core.model import Game
from aidm.core.tools import MasterTool, NoArgs, master_tool
from aidm.kits.entities import Entity, entity_fact
from aidm.kits.scenes.boundary import SCENE_SETTLED
from aidm.kits.scenes.state import SceneState
from aidm.kits.verbs import (
    CHANGE_WORLD,
    TO_PLAYER,
    AddTrait,
    AdvanceThread,
    ImproviseItem,
    JoinParty,
    Kill,
    LeaveParty,
    RemoveTrait,
    Reveal,
    add_trait,
    advance_thread,
    improvise_item,
    join_party,
    leave_party,
    remove_trait,
    reveal,
)

TO_SCENE = "scene"


class Enter(Frozen):
    """Bring a cast member into the current scene."""

    verb: Literal["enter"]
    entity_id: CheckedEntityId = Field(description="Exact id of a cast member not already here.")


class Leave(Frozen):
    """Take a cast member out of the current scene."""

    verb: Literal["leave"]
    entity_id: CheckedEntityId = Field(description="Exact id of someone here.")


class MoveItem(Frozen):
    """Move an item: to the player, to someone here, or loose in the scene."""

    verb: Literal["move_item"]
    item_id: CheckedEntityId = Field(description="Exact id of an item here or carried.")
    to: CheckedEntityId = Field(description="`player`, `scene`, or the exact id of an actor here.")


# A plain alias, not `type`: the union must flatten so the discriminator sees every arm.
WorldChange = (
    Reveal
    | Enter
    | Leave
    | MoveItem
    | ImproviseItem
    | AddTrait
    | RemoveTrait
    | Kill
    | JoinParty
    | LeaveParty
    | AdvanceThread
)


class ChangeWorld(Frozen):
    change: WorldChange = Field(
        discriminator="verb",
        description="The one world change to apply; `verb` picks the change.",
    )


def apply_change[S: BaseModel](world: SceneState[S], change: WorldChange) -> list[Fact]:
    """Every arm settles its own deterministic consequences, so a call leaves nothing half-done."""
    run = world.run
    match change:
        case Reveal():
            one = world.require(change.entity_id)
            if change.entity_id not in run.hidden:
                raise ValueError(f"{change.entity_id!r} is not hidden here")
            run.hidden.remove(one.id)
            run.present.append(one.id)
            return reveal(world, one)
        case Enter():
            one = world.require(change.entity_id)
            if one.id in run.present:
                raise ValueError(f"{one.name} is already here")
            if one.id in run.hidden:
                raise ValueError(f"{one.name} is hidden here; reveal them instead")
            run.present.append(one.id)
            seen = world.reveal(one)
            trace = f"{world.label(one)} arrives"
            return [*seen, entity_fact(one, "entity_entered", trace, card=f"{one.name} arrives")]
        case Leave():
            one = _here(world, world.require(change.entity_id))
            if one.id == world.player_id:
                raise ValueError("the player is in every scene; move the story on instead")
            run.present.remove(one.id)
            trace = f"{world.label(one)} leaves"
            return [entity_fact(one, "entity_left", trace, card=f"{one.name} leaves")]
        case MoveItem():
            return _move_item(world, change)
        case ImproviseItem():
            item, facts = improvise_item(world, change, lambda: None)
            run.present.append(item.id)
            return facts
        case AddTrait():
            return add_trait(world, _acted_on(world, change.entity_id), change)
        case RemoveTrait():
            return remove_trait(world, _acted_on(world, change.entity_id), change)
        case Kill():
            return _kill(world, change.actor_id)
        case JoinParty():
            return join_party(world, change)
        case LeaveParty():
            return leave_party(world, change)
        case AdvanceThread():
            facts = advance_thread(world, change)
            if change.status == "resolved":
                run.spent = f"the thread {world.threads[change.thread_id].title!r} resolved"
            return facts


def scene_tools[G: Game[Any], S: BaseModel](
    world_of: Callable[[G], SceneState[S]],
) -> tuple[MasterTool[G], ...]:
    """The scene kit's complete world-tool surface."""
    change_world: MasterTool[G] = master_tool(
        "change_world",
        CHANGE_WORLD,
        ChangeWorld,
        lambda draft, one, _rng: apply_change(world_of(draft), one.change),
        during_suspension=True,
    )
    next_scene: MasterTool[G] = master_tool(
        "next_scene",
        "Say this scene's question is settled. The player is then asked what they want to "
        "pursue, and their own words build the next scene. Do not answer for them.",
        NoArgs,
        lambda draft, _args, _rng: offer_the_way_on(world_of(draft)),
    )
    return change_world, next_scene


def offer_the_way_on[S: BaseModel](world: SceneState[S]) -> tuple[Fact, ...]:
    if world.run.settled:
        raise ValueError("this scene is already settled; the player has the way on")
    world.run.settled = True
    return (SCENE_SETTLED,)


def _here[S: BaseModel](world: SceneState[S], one: Entity[S]) -> Entity[S]:
    if one.id not in world.run.present:
        raise ValueError(f"{one.name} is not here with the player, so nothing can happen to them")
    return one


def _acted_on[S: BaseModel](world: SceneState[S], entity_id: EntityId) -> Entity[S]:
    """An actor must be here and alive; a thing only has to be here."""
    one = world.require(entity_id)
    return world.require_actor_here(entity_id) if one.kind == "actor" else _here(world, one)


def _move_item[S: BaseModel](world: SceneState[S], change: MoveItem) -> list[Fact]:
    item = world.require_kind(change.item_id, "item")
    if item.carried_by is None and item.id not in world.run.present:
        raise ValueError(f"{item.name} is not here, and nobody is carrying it")
    holder_id = world.player_id if change.to == TO_PLAYER else None
    if change.to not in (TO_PLAYER, TO_SCENE):
        holder_id = _here(world, world.require_kind(EntityId(change.to), "actor")).id
    if item.carried_by == holder_id:
        where = "already lying here" if holder_id is None else f"already held by {change.to}"
        raise ValueError(f"{item.name} is {where}")
    seen = world.reveal(item)
    if change.to == TO_PLAYER:
        item.carried_by = world.player_id
        trace, card = f"the player took {world.label(item)}", f"Took {item.name}"
    elif change.to == TO_SCENE:
        item.carried_by = None
        trace, card = f"{world.label(item)} is left here", f"Left {item.name} here"
    else:
        holder = world.require(EntityId(change.to))
        item.carried_by = holder.id
        trace = f"{world.label(item)} passes to {world.label(holder)}"
        card = f"Gave {item.name} to {holder.name}"
    if item.id not in world.run.present:
        world.run.present.append(item.id)
    return [*seen, entity_fact(item, "entity_moved", trace, card=card)]


def _kill[S: BaseModel](world: SceneState[S], actor_id: EntityId) -> list[Fact]:
    one = _here(world, world.require_kind(actor_id, "actor"))
    if one.trait(DEAD) is not None:
        raise ValueError(f"{one.name} is already dead")
    facts = world.reveal(one)
    if one.id in world.companions:
        world.companions.remove(one.id)
    one.traits.append(Trait(id=DEAD, name="Dead"))
    dropped = list(world.carried_by(one.id))
    for held in dropped:
        held.carried_by = None
    if dropped:
        here = world.run.present
        here.extend([held.id for held in dropped if held.id not in here])
        named = ", ".join(world.label(held) for held in dropped)
        # Untold: a dropped item may still be unrevealed, and its name must not reach the narrator.
        facts.append(Fact(kind="items_dropped", trace=f"{named} fell loose here"))
    trace = f"{world.label(one)} is dead"
    facts.append(entity_fact(one, "actor_killed", trace, card=f"{one.name} is dead"))
    return facts
