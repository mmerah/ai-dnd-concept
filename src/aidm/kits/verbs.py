from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from aidm.core.entities import DEAD, CheckedEntityId, EntityId, Frozen, Slug, Trait, slug
from aidm.core.facts import Fact
from aidm.kits.entities import Entity, Thread, ThreadStatus, World, entity_fact

TO_PLAYER = "player"

CHANGE_WORLD = (
    "Apply one settled world change to match the story. Set `verb` to pick the change and fill "
    "that verb's own fields. One call makes one change."
)


class Reveal(Frozen):
    """Make a hidden entity known when the player notices, finds, or reaches it."""

    verb: Literal["reveal"]
    entity_id: CheckedEntityId = Field(description="Exact id of an entity listed as hidden here.")


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
    """Update an active storyline's status or the line the player reads about it."""

    verb: Literal["advance_thread"]
    thread_id: Slug = Field(description="Exact id of an active thread.")
    status: ThreadStatus | None = Field(
        default=None, description="New status, or null to keep the current status."
    )
    note: str | None = Field(
        default=None,
        description="What the player now knows about this thread, or the lead they have on it, "
        "in one sentence. The player reads this. Null keeps the current note.",
    )


def reveal[S: BaseModel](world: World[S], one: Entity[S]) -> list[Fact]:
    """Each kit decides what the player can reach; the discovery itself reads the same."""
    facts = world.reveal(one)
    if not facts:
        raise ValueError(f"the player has already met {one.name}")
    return [facts[0].model_copy(update={"card": _sentence(f"{one.name} discovered")})]


def improvise_item[S: BaseModel](
    world: World[S], change: ImproviseItem, default_sheet: Callable[[], S | None]
) -> tuple[Entity[S], list[Fact]]:
    """Returns the item too: a kit that tracks presence separately has to file it."""
    item_id = EntityId(slug(change.name, world.cast))
    item = Entity[S](
        id=item_id,
        kind="item",
        name=change.name,
        brief=change.name,
        known=True,
        sheet=default_sheet(),
        carried_by=world.player_id,
    )
    world.cast[item_id] = item
    trace = f"new item: {world.label(item)}"
    return item, [entity_fact(item, "entity_created", trace, card=f"Took {item.name}")]


def add_trait[S: BaseModel](world: World[S], one: Entity[S], change: AddTrait) -> list[Fact]:
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
    return [entity_fact(one, "trait_added", trace, card=f"{one.name}: new trait {change.name}")]


def remove_trait[S: BaseModel](world: World[S], one: Entity[S], change: RemoveTrait) -> list[Fact]:
    held = one.trait(change.trait_id)
    if held is None:
        carried = ", ".join(sorted(trait.id for trait in one.traits)) or "(none)"
        raise ValueError(
            f"{one.name} carries no trait {change.trait_id!r}. Their traits are: {carried}"
        )
    one.traits.remove(held)
    trace = f"{world.label(one)} lost the trait {held.name}[{held.id}]"
    return [entity_fact(one, "trait_removed", trace, card=f"{one.name}: trait {held.name} lifted")]


def join_party[S: BaseModel](world: World[S], change: JoinParty) -> list[Fact]:
    one = world.require_actor_here(change.actor_id)
    if one.id in world.companions:
        raise ValueError(f"{one.name} already travels with the player")
    seen = world.reveal(one)
    world.companions.append(one.id)
    trace = f"{world.label(one)} travels with the player"
    return [*seen, entity_fact(one, "party_joined", trace, card=f"{one.name} joins your party")]


def leave_party[S: BaseModel](world: World[S], change: LeaveParty) -> list[Fact]:
    one = world.require_kind(change.actor_id, "actor")
    if one.id not in world.companions:
        raise ValueError(f"{one.name} does not travel with the player")
    world.companions.remove(one.id)
    trace = f"{world.label(one)} no longer travels with the player"
    return [entity_fact(one, "party_left", trace, card=f"{one.name} leaves your party")]


def advance_thread[S: BaseModel](world: World[S], change: AdvanceThread) -> list[Fact]:
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
    moved = f"thread {thread.title}[{thread.id}] — status {thread.status}"
    if thread.note:
        moved += f" — note: {thread.note}"
    return [Fact(kind="thread_advanced", trace=moved)]


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]
