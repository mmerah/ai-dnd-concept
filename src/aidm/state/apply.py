from collections.abc import Callable, Mapping, Sequence

from pydantic import JsonValue

from .base import PLAYER_ID, Entity, EntityId, Kind, Slug, slug
from .effects import (
    WORLD_OPS,
    AddRef,
    AdvanceThread,
    CounterChange,
    Effect,
    GainImprovisedItem,
    GrantCounter,
    Move,
    Refill,
    RelationChange,
    Reveal,
    SetNote,
    SetNumber,
    TagChange,
)
from .facts import CORE, Fact
from .sheet import Counter, Sheet, SheetTag, pool
from .world import CONNECTED, LOCKED_TAG, PARTY_MEMBER, GameState, Hook, Relation, sheet_of


def apply_effect(
    draft: GameState,
    effect: Effect,
    default_rules: Callable[[Entity], Sheet],
    *,
    advancing: bool = False,
) -> list[Fact]:
    _permitted(effect, advancing=advancing)
    match effect:
        case Reveal(entity_id=entity_id):
            return draft.reveal(_require(draft, entity_id))
        case Move():
            return _move(draft, effect)
        case GainImprovisedItem(item_name=item_name):
            return _improvise(draft, item_name, default_rules)
        case CounterChange(mode="adjust"):
            return _adjust(draft, effect)
        case CounterChange():
            return _spend(draft, effect)
        case GrantCounter():
            return _grant(draft, effect)
        case Refill():
            return _refill(draft, effect)
        case TagChange(mode="add"):
            return _add_tag(draft, effect)
        case TagChange():
            return _remove_tag(draft, effect)
        case SetNote():
            return _set_note(draft, effect)
        case SetNumber():
            return _set_number(draft, effect, advancing=advancing)
        case AddRef():
            return _add_ref(draft, effect)
        case RelationChange(mode="add"):
            return _add_relation(draft, effect)
        case RelationChange(mode="remove"):
            return _remove_relation(draft, effect)
        case RelationChange(mode="untag"):
            return _untag_relation(draft, effect)
        case RelationChange():
            return _reveal_relation(draft, effect)
        case AdvanceThread():
            return _advance_thread(draft, effect)


def _permitted(effect: Effect, *, advancing: bool) -> None:
    if advancing:
        # A denylist suffices: `SheetDelta` validation is what actually bounds this surface.
        if isinstance(effect, (*WORLD_OPS, Refill)):
            raise ValueError(f"{effect.op!r} changes the world; advancement writes only the sheet")
        if effect.entity_id != PLAYER_ID:
            raise ValueError(f"advancement writes {PLAYER_ID!r}, not {effect.entity_id!r}")
        return
    if isinstance(effect, (GrantCounter, AddRef)):
        raise ValueError(f"{effect.op!r} belongs to advancement, not to a turn")
    if isinstance(effect, CounterChange) and effect.maximum is not None:
        raise ValueError("a turn moves a pool inside its bounds; only advancement raises a maximum")


def require_actor_here(state: GameState, actor_id: EntityId | None) -> Entity:
    if actor_id is None or actor_id == PLAYER_ID:
        return state.player
    actor = _require_kind(state, actor_id, "actor")
    if not state.is_here(actor):
        raise ValueError(
            f"{actor_id!r} is not here with the player. "
            "Move them here first, or act on who is here."
        )
    return actor


def _require(state: GameState, entity_id: EntityId) -> Entity:
    entity = state.world.find(entity_id)
    if entity is None:
        raise ValueError(f"unknown entity id {entity_id!r}. Use only ids you were shown.")
    return entity


def _require_kind(state: GameState, entity_id: EntityId, kind: Kind) -> Entity:
    entity = _require(state, entity_id)
    if entity.kind != kind:
        raise ValueError(
            f"{entity_id!r} is a {entity.kind}, not a {kind}. "
            "Use an id of the kind this field asks for."
        )
    return entity


def _counter_of(sheet: Sheet, entity: Entity, key: str) -> Counter:
    held = sheet.counters.get(key)
    if held is None:
        known = ", ".join(sorted(sheet.counters)) or "(none)"
        raise ValueError(f"{entity.name} has no counter {key!r}. Their counters are: {known}")
    return held


def entity_fact(
    entity: Entity, kind: str, trace: str, data: Mapping[str, JsonValue], *, narrate: bool = True
) -> Fact:
    """An entity the player has not learned of narrates nothing, so no unknown name leaks."""
    return Fact(
        source=CORE,
        kind=kind,
        trace=trace,
        narrator=trace if narrate and entity.known else None,
        data={"entity_id": entity.id, **data},
    )


def _target(draft: GameState, entity_id: EntityId) -> tuple[Entity, Sheet, list[Fact]]:
    """A place or a thing is not revealed by being acted on, so no unlearned name leaks."""
    entity = _require(draft, entity_id)
    seen = draft.reveal(require_actor_here(draft, entity_id)) if entity.kind == "actor" else []
    return entity, sheet_of(draft, entity_id), seen


def _require_exit(draft: GameState, here: EntityId, destination: Entity) -> None:
    """A world that authors no connections keeps free movement; one that authors any gates on
    them, so the refusal can teach the model the legal exits."""
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
        moving = _require(draft, effect.entity_id)
        if moving.kind == "item":
            return _move_item(draft, moving, effect.to_id)
    return _move_actor(draft, effect)


def _move_actor(draft: GameState, effect: Move) -> list[Fact]:
    if effect.to_id is None:
        raise ValueError("an actor moves to a location; name it in `to_id`")
    destination = _require_kind(draft, effect.to_id, "location")
    here = draft.player_location
    actor_id = effect.entity_id
    if actor_id is None or actor_id == PLAYER_ID:
        _require_exit(draft, here, destination)
        facts = [*draft.reveal(destination), draft.move(draft.player, destination)]
        for member_id in draft.world.party():
            member = draft.world.require_kind(member_id, "actor")
            if member.parent_id != destination.id:
                facts.append(draft.move(member, destination))
        return facts
    actor = _require_kind(draft, actor_id, "actor")
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
    receiver = _require(draft, to_id)
    if receiver.kind == "location":
        if receiver.id != draft.player_location:
            raise ValueError("an item is set down at the player's own location, nowhere else")
    else:
        receiver = require_actor_here(draft, to_id)
    if item.parent_id != PLAYER_ID:
        raise ValueError(f"the player does not carry item {item.id!r}")
    return [*draft.reveal(item), draft.move(item, receiver)]


def _improvise(
    draft: GameState, item_name: str, default_rules: Callable[[Entity], Sheet]
) -> list[Fact]:
    item = Entity(
        id=slug(item_name, draft.world.all_ids()),
        kind="item",
        name=item_name,
        brief=item_name,
        known=True,
        parent_id=draft.player_location,
    )
    created = draft.add(item, default_rules(item))
    return [created, draft.move(item, draft.player)]


def _adjust(draft: GameState, effect: CounterChange) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    held = _counter_of(sheet, entity, effect.counter)
    if effect.maximum is not None:
        held.maximum = effect.maximum
    before = held.current
    held.current = held.clamped(before + effect.amount)
    landed = held.current - before
    if landed == 0 and effect.maximum is None:
        return seen
    return [*seen, _changed(entity, effect.counter, held, landed, effect.why)]


def _spend(draft: GameState, effect: CounterChange) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    held = _counter_of(sheet, entity, effect.counter)
    if held.current - effect.amount < held.minimum:
        raise ValueError(
            f"{entity.name} holds {held.current} {effect.counter} and cannot go below "
            f"{held.minimum}, so {effect.amount} cannot be spent."
        )
    held.current -= effect.amount
    why = effect.why or f"spent {effect.counter}"
    return [*seen, _changed(entity, effect.counter, held, -effect.amount, why)]


def _grant(draft: GameState, effect: GrantCounter) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if effect.counter in sheet.counters:
        raise ValueError(f"{entity.name} already has {effect.counter!r}; adjust it instead")
    granted = Counter(
        current=effect.current,
        maximum=effect.maximum,
        minimum=effect.minimum,
        recharge=effect.recharge,
    )
    sheet.counters[effect.counter] = granted
    trace = f"{entity.name} gains {effect.counter} at {pool(granted)}"
    data = {"counter": effect.counter, "current": granted.current, "maximum": granted.maximum}
    return [
        *seen,
        _explained_fact(entity, "counter_granted", trace, data, effect.why, narrate=False),
    ]


def _refill(draft: GameState, effect: Refill) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    keys: list[str] = []
    for key, counter in sorted(sheet.counters.items()):
        maximum = counter.maximum
        if maximum is None or counter.recharge not in effect.recharges:
            continue
        if counter.current == maximum:
            continue
        counter.current = maximum
        keys.append(key)
    if not keys:
        return seen
    trace = f"{entity.name} took {effect.label}: refilled {', '.join(keys)}"
    data: Mapping[str, JsonValue] = {"label": effect.label, "counters": list(keys)}
    return [*seen, entity_fact(entity, "recharged", trace, data)]


def _add_tag(draft: GameState, effect: TagChange) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if sheet.tag(effect.tag_id) is not None:
        raise ValueError(f"{entity.name} already carries the tag {effect.tag_id!r}")
    name = effect.tag_id.replace("-", " ").title()
    sheet.tags.append(SheetTag(id=effect.tag_id, name=name, text=effect.text))
    trace = f"{entity.name} is {name}"
    return [
        *seen,
        _explained_fact(entity, "tag_added", trace, {"tag_id": effect.tag_id}, effect.why),
    ]


def _remove_tag(draft: GameState, effect: TagChange) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    tag = sheet.tag(effect.tag_id)
    if tag is None:
        held = ", ".join(sorted(carried.id for carried in sheet.tags)) or "(none)"
        raise ValueError(f"{entity.name} carries no tag {effect.tag_id!r}. Their tags are: {held}")
    sheet.tags.remove(tag)
    trace = f"{entity.name} is no longer {tag.name}"
    data = {"tag_id": effect.tag_id}
    return [*seen, _explained_fact(entity, "tag_removed", trace, data, effect.why)]


def _set_note(draft: GameState, effect: SetNote) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if not effect.text:
        if sheet.notes.pop(effect.key, None) is None:
            return seen
        trace = f"{entity.name} note {effect.key} cleared"
    else:
        sheet.notes[effect.key] = effect.text
        trace = f"{entity.name} note {effect.key}: {effect.text}"
    data = {"key": effect.key}
    return [*seen, _explained_fact(entity, "note_set", trace, data, effect.why, narrate=False)]


def _set_number(draft: GameState, effect: SetNumber, *, advancing: bool) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if not advancing and effect.key not in sheet.numbers:
        held = ", ".join(sorted(sheet.numbers)) or "(none)"
        raise ValueError(f"{entity.name} has no number {effect.key!r}. Their numbers are: {held}")
    before = sheet.numbers.get(effect.key)
    sheet.numbers[effect.key] = effect.value
    trace = f"{entity.name} {effect.key}: {before} -> {effect.value}"
    data = {"key": effect.key, "before": before, "after": effect.value}
    return [*seen, _explained_fact(entity, "number_set", trace, data, effect.why, narrate=False)]


def _add_ref(draft: GameState, effect: AddRef) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if effect.ref in sheet.refs:
        raise ValueError(f"{entity.name} already holds content {effect.ref}")
    sheet.refs = (*sheet.refs, effect.ref)
    trace = f"{entity.name} gains content {effect.ref}"
    data = {"ref": str(effect.ref)}
    return [*seen, _explained_fact(entity, "ref_added", trace, data, effect.why, narrate=False)]


def _relation_of(
    draft: GameState, kind: Slug, source: EntityId, target: EntityId
) -> tuple[Relation, Entity, Entity]:
    relation = draft.world.relation(kind, source, target)
    if relation is None:
        raise ValueError(f"no {kind!r} relation joins {source!r} and {target!r}")
    return relation, draft.world.require(relation.source), draft.world.require(relation.target)


def _add_relation(draft: GameState, effect: RelationChange) -> list[Fact]:
    if draft.world.relation(effect.kind, effect.source, effect.target) is not None:
        raise ValueError(
            f"a {effect.kind!r} relation already joins {effect.source!r} and {effect.target!r}"
        )
    source = (
        require_actor_here(draft, effect.source)
        if effect.kind == PARTY_MEMBER
        else _require(draft, effect.source)
    )
    target = _require(draft, effect.target)
    relation = Relation(
        kind=effect.kind,
        source=effect.source,
        target=effect.target,
        # a connection is walkable both ways, so `connected` is the one undirected kind
        directed=effect.kind != CONNECTED,
        known=True,
    )
    seen = [*draft.reveal(source), *draft.reveal(target)]
    draft.world.relations[relation.id] = relation
    trace = f"{source.name} — {relation.kind} — {target.name}"
    data = {"kind": relation.kind, "target": relation.target}
    return [*seen, _explained_fact(source, "relation_added", trace, data, effect.why)]


def _remove_relation(draft: GameState, effect: RelationChange) -> list[Fact]:
    relation, source, target = _relation_of(draft, effect.kind, effect.source, effect.target)
    del draft.world.relations[relation.id]
    trace = f"{source.name} — {relation.kind} — {target.name} broken"
    data = {"kind": relation.kind, "target": relation.target}
    return [
        _explained_fact(source, "relation_removed", trace, data, effect.why, narrate=relation.known)
    ]


def _untag_relation(draft: GameState, effect: RelationChange) -> list[Fact]:
    relation, source, target = _relation_of(draft, effect.kind, effect.source, effect.target)
    if effect.tag not in relation.tags:
        held = ", ".join(sorted(relation.tags)) or "(none)"
        raise ValueError(
            f"the {relation.kind!r} relation carries no tag {effect.tag!r}. Its tags are: {held}"
        )
    relation.tags.remove(effect.tag)
    trace = f"{source.name} — {relation.kind} — {target.name} untagged {effect.tag}"
    data = {"kind": relation.kind, "target": relation.target, "tag": effect.tag}
    return [
        _explained_fact(
            source, "relation_untagged", trace, data, effect.why, narrate=relation.known
        )
    ]


def _reveal_relation(draft: GameState, effect: RelationChange) -> list[Fact]:
    relation, source, target = _relation_of(draft, effect.kind, effect.source, effect.target)
    if relation.known:
        return []
    seen = [*draft.reveal(source), *draft.reveal(target)]
    relation.known = True
    trace = f"{source.name} — {relation.kind} — {target.name} revealed"
    data = {"kind": relation.kind, "target": relation.target}
    return [*seen, _explained_fact(source, "relation_revealed", trace, data, effect.why)]


def _advance_thread(draft: GameState, effect: AdvanceThread) -> list[Fact]:
    """Threads are the Director's bookkeeping, so nothing here reaches the Narrator."""
    thread = draft.threads.get(effect.thread_id)
    if thread is None:
        known = ", ".join(sorted(draft.threads)) or "(none)"
        raise ValueError(f"unknown thread {effect.thread_id!r}. The threads are: {known}")
    thread.status = effect.status or thread.status
    thread.stage = effect.stage or thread.stage
    moved = f"{thread.title} is {thread.status}" + (f" at {thread.stage}" if thread.stage else "")
    return [
        Fact(
            source=CORE,
            kind="thread_advanced",
            trace=f"{moved} ({effect.why})" if effect.why else moved,
            data={"thread_id": thread.id, "status": thread.status, "stage": thread.stage},
        )
    ]


def fire_hooks(
    draft: GameState, facts: Sequence[Fact], default_rules: Callable[[Entity], Sheet]
) -> list[Fact]:
    """One pass over unfired hooks per turn; chaining happens across turns, never as a fixpoint."""
    fired: list[Fact] = []
    for hook in draft.hooks:
        if hook.id in draft.fired_hooks or not any(hook.match.matches(fact) for fact in facts):
            continue
        draft.fired_hooks = (*draft.fired_hooks, hook.id)
        fired.append(_hook_fact(hook, "hook_fired", f"hook {hook.id} fired"))
        for effect in hook.effects:
            try:
                fired.extend(apply_effect(draft, effect, default_rules))
            except ValueError as refused:
                fired.append(_hook_fact(hook, "hook_failed", f"hook {hook.id} stopped: {refused}"))
                break
        if hook.note:
            draft.pending_notes = (*draft.pending_notes, hook.note)
    return fired


def _hook_fact(hook: Hook, kind: str, trace: str) -> Fact:
    return Fact(source=CORE, kind=kind, trace=trace, data={"hook_id": hook.id})


def _changed(entity: Entity, key: str, counter: Counter, delta: int, why: str) -> Fact:
    data = {"counter": key, "delta": delta, "current": counter.current, "maximum": counter.maximum}
    trace = f"{entity.name} {key} {delta:+d} -> {pool(counter)}"
    return _explained_fact(entity, "counter_changed", trace, data, why)


def _explained_fact(
    entity: Entity,
    kind: str,
    trace: str,
    data: Mapping[str, JsonValue],
    why: str,
    *,
    narrate: bool = True,
) -> Fact:
    """The `why` is what the advancement panel shows the player before they confirm."""
    return entity_fact(entity, kind, f"{trace} ({why})" if why else trace, data, narrate=narrate)
