from typing import Literal

from pydantic import BaseModel, Field

from aidm.kits.scenes.state import (
    Entity,
    SceneState,
    Thread,
    ThreadStatus,
    entity_fact,
)
from aidm.state.entities import DEAD, CheckedEntityId, EntityId, Frozen, Slug, Trait, slug
from aidm.state.facts import Fact
from aidm.state.tools import DirectorTool, director_tool

TO_PLAYER = "player"
TO_SCENE = "scene"


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


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


class ImproviseItem(Frozen):
    """Give the player an ordinary object not already in the world."""

    verb: Literal["improvise_item"]
    name: str = Field(min_length=1, description="The object's name, such as `a handful of gravel`.")


class AddTrait(Frozen):
    """Add a lasting condition or quality to an entity."""

    verb: Literal["add_trait"]
    entity_id: CheckedEntityId = Field(description="Exact entity id. An actor must be here.")
    name: str = Field(min_length=1, description="Display name, such as `Battle Worn`.")
    text: str = Field(description="The effect in plain language.")


class RemoveTrait(Frozen):
    """Remove a lasting condition that has ended."""

    verb: Literal["remove_trait"]
    entity_id: CheckedEntityId = Field(description="Exact entity id.")
    trait_id: Slug = Field(description="Exact id of one of its traits.")


class Kill(Frozen):
    """Record that an actor has died. What they carried falls loose here."""

    verb: Literal["kill"]
    actor_id: CheckedEntityId = Field(description="Exact id of the actor here who died.")


class JoinParty(Frozen):
    """An actor here starts travelling with the player."""

    verb: Literal["join_party"]
    actor_id: CheckedEntityId = Field(description="Exact id of the actor joining.")


class LeaveParty(Frozen):
    """A companion stops travelling with the player."""

    verb: Literal["leave_party"]
    actor_id: CheckedEntityId = Field(description="Exact id of the companion leaving.")


class AdvanceThread(Frozen):
    """Update an active storyline's status or private note."""

    verb: Literal["advance_thread"]
    thread_id: Slug = Field(description="Exact id of an active thread.")
    status: ThreadStatus | None = Field(
        default=None, description="New status, or null to keep the current status."
    )
    note: str | None = Field(
        default=None, description="New private note, or null to keep the current note."
    )


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


def _here[S: BaseModel](world: SceneState[S], one: Entity[S]) -> Entity[S]:
    if one.id not in world.current.present:
        raise ValueError(f"{one.name} is not here with the player, so nothing can happen to them")
    return one


def _acted_on[S: BaseModel](world: SceneState[S], entity_id: EntityId) -> Entity[S]:
    """An actor must be here and alive; a thing only has to be here."""
    one = world.require(entity_id)
    return world.require_actor_here(entity_id) if one.kind == "actor" else _here(world, one)


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def apply_change[S: BaseModel](world: SceneState[S], change: WorldChange) -> list[Fact]:  # noqa: C901
    """Every arm settles its own deterministic consequences, so a call leaves nothing half-done."""
    scene = world.current
    match change:
        case Reveal():
            one = world.require(change.entity_id)
            if change.entity_id not in scene.hidden:
                raise ValueError(f"{change.entity_id!r} is not hidden here")
            world.current = scene.model_copy(
                update={
                    "hidden": tuple(x for x in scene.hidden if x != one.id),
                    "present": (*scene.present, one.id),
                }
            )
            facts = world.reveal(one)
            if not facts:
                raise ValueError(f"the player has already met {one.name}")
            return [facts[0].model_copy(update={"card": _sentence(f"{one.name} discovered")})]
        case Enter():
            one = world.require(change.entity_id)
            if one.id in scene.present:
                raise ValueError(f"{one.name} is already here")
            if one.id in scene.hidden:
                raise ValueError(f"{one.name} is hidden here; reveal them instead")
            world.current = scene.model_copy(update={"present": (*scene.present, one.id)})
            seen = world.reveal(one)
            trace = f"{world.label(one)} arrives"
            return [*seen, entity_fact(one, "entity_entered", trace, card=f"{one.name} arrives")]
        case Leave():
            one = _here(world, world.require(change.entity_id))
            if one.id == world.player_id:
                raise ValueError("the player is in every scene; move the story on instead")
            world.current = scene.model_copy(
                update={"present": tuple(x for x in scene.present if x != one.id)}
            )
            trace = f"{world.label(one)} leaves"
            return [entity_fact(one, "entity_left", trace, card=f"{one.name} leaves")]
        case MoveItem():
            return _move_item(world, change)
        case ImproviseItem():
            new_id = EntityId(slug(change.name, world.cast))
            item = Entity[S](
                id=new_id,
                kind="item",
                name=change.name,
                brief=change.name,
                known=True,
                carried_by=world.player_id,
            )
            world.cast[new_id] = item
            world.current = scene.model_copy(update={"present": (*scene.present, new_id)})
            trace = f"new item: {world.label(item)}"
            return [entity_fact(item, "entity_created", trace, card=f"Took {item.name}")]
        case AddTrait():
            one = _acted_on(world, change.entity_id)
            trait_id = slug(change.name, ())
            # Only `kill` may end a life: it drops what the dead carried.
            if trait_id == DEAD:
                raise ValueError(f"call kill to record a death, not add_trait with {change.name!r}")
            if one.trait(trait_id) is not None:
                raise ValueError(f"{one.name} already carries the trait {change.name!r}")
            one.traits.append(Trait(id=trait_id, name=change.name, text=change.text))
            trace = f"{world.label(one)} gained the trait {change.name}[{trait_id}]"
            if change.text:
                trace += f" — {change.text}"
            card = f"{one.name} gained {change.name}"
            return [entity_fact(one, "trait_added", trace, card=card)]
        case RemoveTrait():
            one = _acted_on(world, change.entity_id)
            held = one.trait(change.trait_id)
            if held is None:
                carried = ", ".join(sorted(t.id for t in one.traits)) or "(none)"
                raise ValueError(
                    f"{one.name} carries no trait {change.trait_id!r}. Their traits are: {carried}"
                )
            one.traits.remove(held)
            trace = f"{world.label(one)} lost the trait {held.name}[{held.id}]"
            return [entity_fact(one, "trait_removed", trace, card=f"{one.name} lost {held.name}")]
        case Kill():
            return _kill(world, change.actor_id)
        case JoinParty():
            one = _here(world, world.require_kind(change.actor_id, "actor"))
            if one.id in world.companions:
                raise ValueError(f"{one.name} already travels with the player")
            seen = world.reveal(one)
            world.companions.append(one.id)
            trace = f"{world.label(one)} travels with the player"
            card = f"{one.name} joins your party"
            return [*seen, entity_fact(one, "party_joined", trace, card=card)]
        case LeaveParty():
            one = world.require_kind(change.actor_id, "actor")
            if one.id not in world.companions:
                raise ValueError(f"{one.name} does not travel with the player")
            world.companions.remove(one.id)
            trace = f"{world.label(one)} no longer travels with the player"
            card = f"{one.name} leaves your party"
            return [entity_fact(one, "party_left", trace, card=card)]
        case AdvanceThread():
            return _advance_thread(world, change)


def _move_item[S: BaseModel](world: SceneState[S], change: MoveItem) -> list[Fact]:
    item = world.require_kind(change.item_id, "item")
    if item.carried_by is None and item.id not in world.current.present:
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
    if item.id not in world.current.present:
        world.current = world.current.model_copy(
            update={"present": (*world.current.present, item.id)}
        )
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
        scene = world.current
        loose = tuple(held.id for held in dropped if held.id not in scene.present)
        world.current = scene.model_copy(update={"present": (*scene.present, *loose)})
        named = ", ".join(world.label(held) for held in dropped)
        # Untold: a dropped item may still be unrevealed, and its name must not reach the narrator.
        facts.append(Fact(kind="items_dropped", trace=f"{named} fell loose here"))
    trace = f"{world.label(one)} is dead"
    facts.append(entity_fact(one, "actor_killed", trace, card=f"{one.name} is dead"))
    return facts


def _advance_thread[S: BaseModel](world: SceneState[S], change: AdvanceThread) -> list[Fact]:
    """Threads are the game master's bookkeeping, so nothing here reaches the narrator."""
    thread: Thread | None = world.threads.get(change.thread_id)
    if thread is None:
        known = ", ".join(sorted(world.threads)) or "(none)"
        raise ValueError(f"unknown thread {change.thread_id!r}. The threads are: {known}")
    if change.status is None and change.note is None:
        raise ValueError("advance_thread moves a thread's status or its note")
    thread.status = change.status or thread.status
    if change.note is not None:
        thread.note = change.note
    if change.status == "resolved":
        world.spent = f"the thread {thread.title!r} resolved"
    moved = f"thread {thread.title}[{thread.id}] — status {thread.status}"
    if thread.note:
        moved += f" — note: {thread.note}"
    return [Fact(kind="thread_advanced", trace=moved)]


CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)


def scene_tools(*extra: DirectorTool) -> tuple[DirectorTool, ...]:
    """Core owns `change_world`; an engine names the procedure tools that follow it."""
    change_world = director_tool(
        "change_world",
        CHANGE_WORLD,
        ChangeWorld,
        lambda draft, one, _rng: apply_change(draft.world, one.change),
        during_suspension=True,
    )
    return (change_world, *extra)
