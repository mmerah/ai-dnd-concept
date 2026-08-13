from collections.abc import Sequence

from pydantic import JsonValue

from .base import PLAYER_ID, Entity, EntityId, Slug, Trait, slug
from .effects import (
    AdvanceThread,
    GainImprovisedItem,
    Move,
    RelationChange,
    Reveal,
    TraitChange,
    WorldEffect,
)
from .facts import CORE, Fact, explained, explained_fact
from .world import CONNECTED, LOCKED_TAG, PARTY_MEMBER, GameState, Hook, Relation


def apply_effect(draft: GameState, effect: WorldEffect) -> list[Fact]:
    match effect:
        case Reveal(entity_id=entity_id):
            return draft.reveal(draft.world.require(entity_id))
        case Move():
            return _move(draft, effect)
        case GainImprovisedItem(item_name=item_name):
            return _improvise(draft, item_name)
        case TraitChange(mode="add"):
            return _add_trait(draft, effect)
        case TraitChange():
            return _remove_trait(draft, effect)
        case RelationChange():
            return _relation_change(draft, effect)
        case AdvanceThread():
            return _advance_thread(draft, effect)


def require_actor_here(state: GameState, actor_id: EntityId | None) -> Entity:
    if actor_id is None or actor_id == PLAYER_ID:
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


def _require_open_way(draft: GameState, here: EntityId, destination: Entity) -> None:
    exits = draft.world.connections(here)
    if not exits:
        return
    found = draft.world.relation(CONNECTED, here, destination.id)
    if found is None:
        open_exits = [
            draft.world.require(way.far_end(here)).name
            for way in exits
            if way.known and LOCKED_TAG not in way.tags
        ]
        reachable = ", ".join(open_exits) or "(none)"
        raise ValueError(
            f"no way leads from here to {destination.name}. From here the player can reach: "
            f"{reachable}"
        )
    if not found.known:
        raise ValueError(
            f"the player has not found the way to {destination.name} yet, so walking it is one "
            "plan, not two: put a `relation-change` with `mode: reveal` for that way immediately "
            "before this move, in the same list"
        )
    if LOCKED_TAG in found.tags:
        raise ValueError(f"the way to {destination.name} is locked and must be dealt with first")


def _move(draft: GameState, effect: Move) -> list[Fact]:
    if effect.entity_id is not None and effect.entity_id != PLAYER_ID:
        moving = draft.world.require(effect.entity_id)
        if moving.kind == "item":
            return _move_item(draft, moving, effect.to_id)
    return _move_actor(draft, effect)


def _move_actor(draft: GameState, effect: Move) -> list[Fact]:
    if effect.to_id is None:
        raise ValueError("an actor moves to a location; name it in `to_id`")
    destination = draft.world.require_kind(effect.to_id, "location")
    here = draft.player_location
    actor_id = effect.entity_id
    if actor_id is None or actor_id == PLAYER_ID:
        _require_open_way(draft, here, destination)
        facts = [*draft.reveal(destination), draft.move(draft.player, destination)]
        for member_id in draft.world.party():
            member = draft.world.require_kind(member_id, "actor")
            if member.parent_id != destination.id:
                facts.append(draft.move(member, destination))
        return facts
    actor = draft.world.require_kind(actor_id, "actor")
    if actor.parent_id != here and destination.id != here:
        raise ValueError(f"movement of actor {actor_id!r} would not be witnessed")
    revealed = draft.reveal(actor) if destination.id == here else []
    return [*revealed, draft.move(actor, destination)]


def _move_item(draft: GameState, item: Entity, to_id: EntityId | None) -> list[Fact]:
    if to_id is None or to_id == PLAYER_ID:
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


def _improvise(draft: GameState, item_name: str) -> list[Fact]:
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


def _add_trait(draft: GameState, effect: TraitChange) -> list[Fact]:
    entity, seen = reveal_target(draft, effect.entity_id)
    if entity.trait(effect.trait_id) is not None:
        raise ValueError(f"{entity.name} already carries the trait {effect.trait_id!r}")
    name = effect.trait_id.replace("-", " ").title()
    entity.traits.append(Trait(id=effect.trait_id, name=name, text=effect.text))
    trace = f"{entity.name} is {name}"
    return [
        *seen,
        explained_fact(entity, "trait_added", trace, {"trait_id": effect.trait_id}, effect.why),
    ]


def _remove_trait(draft: GameState, effect: TraitChange) -> list[Fact]:
    entity, seen = reveal_target(draft, effect.entity_id)
    held = entity.trait(effect.trait_id)
    if held is None:
        carried = ", ".join(sorted(one.id for one in entity.traits)) or "(none)"
        raise ValueError(
            f"{entity.name} carries no trait {effect.trait_id!r}. Their traits are: {carried}"
        )
    entity.traits.remove(held)
    trace = f"{entity.name} is no longer {held.name}"
    data = {"trait_id": effect.trait_id}
    return [*seen, explained_fact(entity, "trait_removed", trace, data, effect.why)]


def _relation_of(
    draft: GameState, kind: Slug, source: EntityId, target_id: EntityId
) -> tuple[Relation, Entity, Entity]:
    relation = draft.world.relation(kind, source, target_id)
    if relation is None:
        raise ValueError(f"no {kind!r} relation joins {source!r} and {target_id!r}")
    return relation, draft.world.require(relation.source), draft.world.require(relation.target)


def _relation_change(draft: GameState, effect: RelationChange) -> list[Fact]:
    seen: list[Fact] = []
    if effect.mode == "add":
        if draft.world.relation(effect.kind, effect.source, effect.target) is not None:
            raise ValueError(
                f"a {effect.kind!r} relation already joins {effect.source!r} and {effect.target!r}"
            )
        source = (
            require_actor_here(draft, effect.source)
            if effect.kind == PARTY_MEMBER
            else draft.world.require(effect.source)
        )
        receiver = draft.world.require(effect.target)
        relation = Relation(
            kind=effect.kind,
            source=effect.source,
            target=effect.target,
            # a connection is walkable both ways, so `connected` is the one undirected kind
            directed=effect.kind != CONNECTED,
            known=True,
        )
        seen = [*draft.reveal(source), *draft.reveal(receiver)]
        draft.world.relations[relation.id] = relation
    else:
        relation, source, receiver = _relation_of(draft, effect.kind, effect.source, effect.target)
    joined = f"{source.name} — {relation.kind} — {receiver.name}"
    data: dict[str, JsonValue] = {"kind": relation.kind, "target": relation.target}
    match effect.mode:
        case "add":
            return [*seen, explained_fact(source, "relation_added", joined, data, effect.why)]
        case "remove":
            del draft.world.relations[relation.id]
            return [
                explained_fact(
                    source,
                    "relation_removed",
                    f"{joined} broken",
                    data,
                    effect.why,
                    narrate=relation.known,
                )
            ]
        case "untag":
            if effect.tag not in relation.tags:
                held = ", ".join(sorted(relation.tags)) or "(none)"
                raise ValueError(
                    f"the {relation.kind!r} relation carries no tag {effect.tag!r}. "
                    f"Its tags are: {held}"
                )
            relation.tags.remove(effect.tag)
            return [
                explained_fact(
                    source,
                    "relation_untagged",
                    f"{joined} untagged {effect.tag}",
                    {**data, "tag": effect.tag},
                    effect.why,
                    narrate=relation.known,
                )
            ]
        case "reveal":
            if relation.known:
                return []
            seen = [*draft.reveal(source), *draft.reveal(receiver)]
            relation.known = True
            return [
                *seen,
                explained_fact(source, "relation_revealed", f"{joined} revealed", data, effect.why),
            ]


def _advance_thread(draft: GameState, effect: AdvanceThread) -> list[Fact]:
    """Threads are the Director's bookkeeping, so nothing here reaches the Narrator."""
    thread = draft.world.threads.get(effect.thread_id)
    if thread is None:
        known = ", ".join(sorted(draft.world.threads)) or "(none)"
        raise ValueError(f"unknown thread {effect.thread_id!r}. The threads are: {known}")
    thread.status = effect.status or thread.status
    thread.stage = effect.stage or thread.stage
    moved = f"{thread.title} is {thread.status}" + (f" at {thread.stage}" if thread.stage else "")
    return [
        Fact(
            source=CORE,
            kind="thread_advanced",
            trace=explained(moved, effect.why),
            data={"thread_id": thread.id, "status": thread.status, "stage": thread.stage},
        )
    ]


def fire_hooks(draft: GameState, facts: Sequence[Fact]) -> list[Fact]:
    """One pass over unfired hooks per turn; chaining happens across turns, never as a fixpoint."""
    fired: list[Fact] = []
    world = draft.world
    for hook in world.hooks:
        if hook.id in world.fired_hooks or not any(hook.match.matches(fact) for fact in facts):
            continue
        world.fired_hooks = (*world.fired_hooks, hook.id)
        fired.append(_hook_fact(hook, "hook_fired", f"hook {hook.id} fired"))
        for effect in hook.effects:
            try:
                fired.extend(apply_effect(draft, effect))
            except ValueError as refused:
                fired.append(_hook_fact(hook, "hook_failed", f"hook {hook.id} stopped: {refused}"))
                break
        if hook.note:
            world.pending_notes = (*world.pending_notes, hook.note)
    return fired


def _hook_fact(hook: Hook, kind: str, trace: str) -> Fact:
    return Fact(source=CORE, kind=kind, trace=trace, data={"hook_id": hook.id})
