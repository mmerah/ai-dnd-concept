from pydantic import JsonValue

from .base import PLAYER_ID, Entity, EntityId, Exit, Slug, Trait, slug
from .facts import Fact, entity_fact
from .world import AdvanceThread, GameState


def reveal(draft: GameState, entity_id: EntityId) -> list[Fact]:
    return draft.reveal(draft.world.require(entity_id))


def require_actor_here(state: GameState, actor_id: EntityId) -> Entity:
    if actor_id == PLAYER_ID:
        return state.player
    actor = state.world.require_kind(actor_id, "actor")
    if not state.is_here(actor):
        raise ValueError(
            f"{actor_id!r} is not here with the player. "
            "Move them here first, or act on who is here."
        )
    return actor


def reveal_target(draft: GameState, entity_id: EntityId) -> tuple[Entity, list[Fact]]:
    """A place or a thing is not revealed by being acted on, so no unlearned name leaks."""
    entity = draft.world.require(entity_id)
    seen = draft.reveal(require_actor_here(draft, entity_id)) if entity.kind == "actor" else []
    return entity, seen


def _walkable_exit(draft: GameState, here: Entity, destination: Entity) -> Exit:
    found = here.exit_to(destination.id)
    if found is None:
        open_exits = [draft.world.require(way.to).name for way in here.exits if not way.locked]
        reachable = ", ".join(open_exits) or "(none)"
        raise ValueError(
            f"no way leads from here to {destination.name}. From here the player can reach: "
            f"{reachable}"
        )
    if found.locked:
        raise ValueError(f"the way to {destination.name} is locked and must be dealt with first")
    return found


def move(draft: GameState, entity_id: EntityId, to_id: EntityId) -> list[Fact]:
    moving = draft.world.require(entity_id)
    if moving.kind == "item":
        return _move_item(draft, moving, to_id)
    return _move_actor(draft, entity_id, to_id)


def _move_actor(draft: GameState, actor_id: EntityId, to_id: EntityId) -> list[Fact]:
    destination = draft.world.require_kind(to_id, "location")
    here = draft.player_location
    if actor_id == PLAYER_ID:
        way = _walkable_exit(draft, draft.world.require(here), destination)
        # Walking a way is finding it, in both directions: the player who arrived can see the
        # door they came through, and the destination is revealed below, so both ends are known.
        way.known = True
        back = destination.exit_to(here)
        if back is not None:
            back.known = True
        facts = [*draft.reveal(destination), draft.move(draft.player, destination)]
        for member_id in draft.world.party:
            member = draft.world.require_kind(member_id, "actor")
            if member.parent_id != destination.id:
                facts.append(draft.move(member, destination))
        return facts
    actor = draft.world.require_kind(actor_id, "actor")
    if actor.parent_id != here and destination.id != here:
        raise ValueError(f"movement of actor {actor_id!r} would not be witnessed")
    revealed = draft.reveal(actor) if destination.id == here else []
    return [*revealed, draft.move(actor, destination)]


def _move_item(draft: GameState, item: Entity, to_id: EntityId) -> list[Fact]:
    if to_id == PLAYER_ID:
        if item.parent_id == PLAYER_ID:
            raise ValueError(f"the player already carries item {item.id!r}")
        if item.parent_id != draft.player_location:
            raise ValueError(f"item {item.id!r} is not loose at the player's location")
        return [*draft.reveal(item), draft.move(item, draft.player)]
    receiver = draft.world.require(to_id)
    if receiver.kind == "location":
        if receiver.id != draft.player_location:
            raise ValueError("an item is set down at the player's own location, nowhere else")
    else:
        receiver = require_actor_here(draft, to_id)
    if item.parent_id != PLAYER_ID:
        raise ValueError(f"the player does not carry item {item.id!r}")
    return [*draft.reveal(item), draft.move(item, receiver)]


def improvise(draft: GameState, item_name: str) -> list[Fact]:
    item = Entity(
        id=slug(item_name, draft.world.all_ids()),
        kind="item",
        name=item_name,
        brief=item_name,
        known=True,
        parent_id=draft.player_location,
    )
    created = draft.add(item)
    return [created, draft.move(item, draft.player)]


def add_trait(draft: GameState, entity_id: EntityId, trait_id: Slug, text: str = "") -> list[Fact]:
    entity, seen = reveal_target(draft, entity_id)
    if entity.trait(trait_id) is not None:
        raise ValueError(f"{entity.name} already carries the trait {trait_id!r}")
    name = trait_id.replace("-", " ").title()
    entity.traits.append(Trait(id=trait_id, name=name, text=text))
    trace = f"{entity.name} is {name}"
    return [*seen, entity_fact(entity, "trait_added", trace, {"trait_id": trait_id})]


def remove_trait(draft: GameState, entity_id: EntityId, trait_id: Slug) -> list[Fact]:
    entity, seen = reveal_target(draft, entity_id)
    held = entity.trait(trait_id)
    if held is None:
        carried = ", ".join(sorted(one.id for one in entity.traits)) or "(none)"
        raise ValueError(
            f"{entity.name} carries no trait {trait_id!r}. Their traits are: {carried}"
        )
    entity.traits.remove(held)
    trace = f"{entity.name} is no longer {held.name}"
    return [*seen, entity_fact(entity, "trait_removed", trace, {"trait_id": trait_id})]


def unlock_exit(draft: GameState, location_id: EntityId, to_id: EntityId) -> list[Fact]:
    here = draft.world.require_kind(location_id, "location")
    there = draft.world.require_kind(to_id, "location")
    way = here.exit_to(to_id)
    if way is None:
        raise ValueError(f"no way leads from {here.name} to {there.name}")
    if not way.locked:
        raise ValueError(f"the way from {here.name} to {there.name} is not locked")
    way.locked = False
    # A lock holds both ways, so leaving the way back shut would strand the player behind it.
    back = there.exit_to(location_id)
    if back is not None:
        back.locked = False
    return [
        entity_fact(
            here,
            "exit_unlocked",
            f"the way from {here.name} to {there.name} is unlocked",
            {"to_id": to_id},
            narrate=way.known,
        )
    ]


def join_party(draft: GameState, actor_id: EntityId) -> list[Fact]:
    actor = require_actor_here(draft, actor_id)
    if actor_id in draft.world.party:
        raise ValueError(f"{actor.name} already travels with the player")
    seen = draft.reveal(actor)
    draft.world.party.append(actor_id)
    return [*seen, entity_fact(actor, "party_joined", f"{actor.name} travels with the player", {})]


def leave_party(draft: GameState, actor_id: EntityId) -> list[Fact]:
    actor = draft.world.require_kind(actor_id, "actor")
    if actor_id not in draft.world.party:
        raise ValueError(f"{actor.name} does not travel with the player")
    draft.world.party.remove(actor_id)
    return [entity_fact(actor, "party_left", f"{actor.name} no longer travels with the player", {})]


def advance_thread(draft: GameState, effect: AdvanceThread) -> list[Fact]:
    """Threads are the Director's bookkeeping, so nothing here reaches the Narrator."""
    thread = draft.world.thread(effect.thread_id)
    if thread is None:
        known = ", ".join(sorted(thread.id for thread in draft.world.threads)) or "(none)"
        raise ValueError(f"unknown thread {effect.thread_id!r}. The threads are: {known}")
    clock = thread.clock
    if effect.tick:
        if clock is None:
            raise ValueError(
                f"the thread {thread.id!r} has no clock to tick. Move its stage or status instead."
            )
        clock.current = clock.clamped(clock.current + effect.tick)
    thread.status = effect.status or thread.status
    thread.stage = effect.stage or thread.stage
    moved = f"{thread.title} is {thread.status}" + (f" at {thread.stage}" if thread.stage else "")
    data: dict[str, JsonValue] = {
        "thread_id": thread.id,
        "status": thread.status,
        "stage": thread.stage,
    }
    if clock is not None:
        moved += f" (clock {clock.current}/{clock.maximum})"
        data |= {
            "clock_current": clock.current,
            "clock_maximum": clock.maximum,
            "clock_filled": clock.current == clock.maximum,
        }
    return [Fact(kind="thread_advanced", trace=moved, data=data)]
