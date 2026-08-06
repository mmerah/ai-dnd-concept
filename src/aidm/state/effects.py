from collections.abc import Callable, Mapping
from typing import Annotated, Literal, get_args

from pydantic import Field, JsonValue

from .base import PLAYER_ID, Entity, EntityId, Frozen, Kind, Slug, slug
from .facts import CORE, Fact
from .sheet import Counter, Sheet, SheetTag, pool
from .world import GameState, sheet_of

TargetId = Annotated[
    EntityId,
    Field(description="Exact id of the entity affected; an actor must be here with the player."),
]
CounterKey = Annotated[
    Slug, Field(description="Exact key of one of that entity's counters, as its sheet spells it.")
]


class Reveal(Frozen):
    """Reveal an entity that exists but the player does not know yet: they notice it, are told of
    it, or reach it. Prefer this over inventing a replacement."""

    op: Literal["reveal"] = "reveal"
    entity_id: EntityId = Field(description="Exact id of the unrevealed canon entity.")


class MoveActor(Frozen):
    """Move an actor who actually changes location. Moving the player to an unrevealed location
    reveals it."""

    op: Literal["move-actor"] = "move-actor"
    entity_id: EntityId | None = Field(
        default=None, description="Exact id of the actor to move; null moves the player."
    )
    location_id: EntityId = Field(description="Exact id of the location the actor enters.")


class MoveItem(Frozen):
    """Move one item within the player's reach: pick it up, set it down here, or hand it to an
    actor here."""

    op: Literal["move-item"] = "move-item"
    item_id: EntityId = Field(
        description="Exact id of the item: one the player carries, or one loose at their location."
    )
    to_id: EntityId | None = Field(
        default=None,
        description="Exact id of the receiver: an actor here with the player, or the player's own "
        "location to set the item down. Null hands the item to the player.",
    )


class GainImprovisedItem(Frozen):
    """Give the player an ordinary incidental object that is not in canon and is not worth a canon
    entry of its own. Never a substitute for an item that already exists."""

    op: Literal["gain-improvised-item"] = "gain-improvised-item"
    item_name: str = Field(
        min_length=1, description="The object written out, such as 'a handful of gravel'."
    )


class AdjustCounter(Frozen):
    """Move a counter up or down. The change is clamped to the counter's own bounds."""

    op: Literal["adjust-counter"] = "adjust-counter"
    entity_id: TargetId
    counter: CounterKey
    delta: int = Field(description="How much the pool moves: negative to reduce.")
    reason: str = Field(min_length=1, description="What changed the pool, in a few words.")


class SpendCounter(Frozen):
    """Pay from a counter, which refuses outright when the pool cannot cover it."""

    op: Literal["spend-counter"] = "spend-counter"
    entity_id: TargetId
    counter: CounterKey
    amount: int = Field(ge=1, description="How much of the pool is spent.")


class AddTag(Frozen):
    """Put a lasting condition, edge, or burden on an entity. The sheet shows the id written
    out: `battle-worn` appears as Battle Worn."""

    op: Literal["add-tag"] = "add-tag"
    entity_id: TargetId
    tag_id: Slug = Field(description="Stable slug for the tag, such as `poisoned`.")
    text: str = Field(
        default="", description="The constraint or benefit it puts on the entity, in prose."
    )


class RemoveTag(Frozen):
    """Lift a tag an entity carries, when the fiction ends it."""

    op: Literal["remove-tag"] = "remove-tag"
    entity_id: TargetId
    tag_id: Slug = Field(description="Exact id of a tag the entity carries.")


class SetNote(Frozen):
    """Write freeform bookkeeping the fiction needs remembered and no counter or tag holds, such as
    what a caster concentrates on. Writing a key again replaces what it held."""

    op: Literal["set-note"] = "set-note"
    entity_id: TargetId
    key: Slug = Field(description="What the note is about, such as `concentration`.")
    text: str = Field(description="The note; empty clears whatever the key held.")


class SetNumber(Frozen):
    """Set a number the fiction has lastingly changed — armour worn, a permanent blessing. Never
    for this turn's outcome: pools that go up and down are counters."""

    op: Literal["set-number"] = "set-number"
    entity_id: TargetId
    key: Slug = Field(description="Exact key of a number already on that sheet.")
    value: int = Field(description="What the number becomes.")


type Effect = Annotated[
    Reveal
    | MoveActor
    | MoveItem
    | GainImprovisedItem
    | AdjustCounter
    | SpendCounter
    | AddTag
    | RemoveTag
    | SetNote
    | SetNumber,
    Field(discriminator="op"),
]


def effect_ops() -> frozenset[str]:
    union, _ = get_args(Effect.__value__)
    return frozenset(member.model_fields["op"].default for member in get_args(union))


def apply_effect(
    draft: GameState, effect: Effect, default_rules: Callable[[Entity], Sheet]
) -> list[Fact]:
    """Mutates the draft, raising `ValueError` with a model-readable reason on a refused
    precondition. There is no separate check: a plan is validated by trial-applying it."""
    match effect:
        case Reveal(entity_id=entity_id):
            return draft.reveal(_require(draft, entity_id))
        case MoveActor():
            return _move_actor(draft, effect)
        case MoveItem():
            return _move_item(draft, effect)
        case GainImprovisedItem(item_name=item_name):
            return _improvise(draft, item_name, default_rules)
        case AdjustCounter():
            return _adjust(draft, effect)
        case SpendCounter():
            return _spend(draft, effect)
        case AddTag():
            return _add_tag(draft, effect)
        case RemoveTag():
            return _remove_tag(draft, effect)
        case SetNote():
            return _set_note(draft, effect)
        case SetNumber():
            return _set_number(draft, effect)


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


def _require_carried(state: GameState, item_id: EntityId) -> Entity:
    item = _require_kind(state, item_id, "item")
    if item.parent_id != PLAYER_ID:
        raise ValueError(f"the player does not carry item {item_id!r}")
    return item


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


def _move_actor(draft: GameState, effect: MoveActor) -> list[Fact]:
    destination = _require_kind(draft, effect.location_id, "location")
    here = draft.player_location
    actor_id = effect.entity_id
    if actor_id is None or actor_id == PLAYER_ID:
        return [*draft.reveal(destination), draft.move(draft.player, destination)]
    actor = _require_kind(draft, actor_id, "actor")
    if actor.parent_id != here and destination.id != here:
        raise ValueError(f"movement of actor {actor_id!r} would not be witnessed")
    revealed = draft.reveal(actor) if destination.id == here else []
    return [*revealed, draft.move(actor, destination)]


def _move_item(draft: GameState, effect: MoveItem) -> list[Fact]:
    to_id = effect.to_id
    if to_id is None or to_id == PLAYER_ID:
        item = _require_kind(draft, effect.item_id, "item")
        if item.parent_id == PLAYER_ID:
            raise ValueError(f"the player already carries item {effect.item_id!r}")
        if item.parent_id != draft.player_location:
            raise ValueError(f"item {effect.item_id!r} is not loose at the player's location")
        return [*draft.reveal(item), draft.move(item, draft.player)]
    receiver = _require(draft, to_id)
    if receiver.kind == "location":
        if receiver.id != draft.player_location:
            raise ValueError("an item is set down at the player's own location, nowhere else")
    else:
        receiver = require_actor_here(draft, to_id)
    item = _require_carried(draft, effect.item_id)
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


def _adjust(draft: GameState, effect: AdjustCounter) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    held = _counter_of(sheet, entity, effect.counter)
    before = held.current
    held.current = held.clamped(before + effect.delta)
    landed = held.current - before
    if landed == 0:
        return seen
    return [*seen, _changed(entity, effect.counter, held, landed, effect.reason)]


def _spend(draft: GameState, effect: SpendCounter) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    held = _counter_of(sheet, entity, effect.counter)
    if held.current - effect.amount < held.minimum:
        raise ValueError(
            f"{entity.name} holds {held.current} {effect.counter} and cannot go below "
            f"{held.minimum}, so {effect.amount} cannot be spent."
        )
    held.current -= effect.amount
    spent = f"spent {effect.counter}"
    return [*seen, _changed(entity, effect.counter, held, -effect.amount, spent)]


def _add_tag(draft: GameState, effect: AddTag) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if sheet.tag(effect.tag_id) is not None:
        raise ValueError(f"{entity.name} already carries the tag {effect.tag_id!r}")
    name = effect.tag_id.replace("-", " ").title()
    sheet.tags.append(SheetTag(id=effect.tag_id, name=name, text=effect.text))
    trace = f"{entity.name} is {name}"
    return [*seen, entity_fact(entity, "tag_added", trace, {"tag_id": effect.tag_id})]


def _remove_tag(draft: GameState, effect: RemoveTag) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    tag = sheet.tag(effect.tag_id)
    if tag is None:
        held = ", ".join(sorted(carried.id for carried in sheet.tags)) or "(none)"
        raise ValueError(f"{entity.name} carries no tag {effect.tag_id!r}. Their tags are: {held}")
    sheet.tags.remove(tag)
    trace = f"{entity.name} is no longer {tag.name}"
    return [*seen, entity_fact(entity, "tag_removed", trace, {"tag_id": effect.tag_id})]


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
    return [*seen, entity_fact(entity, "note_set", trace, data, narrate=False)]


def _set_number(draft: GameState, effect: SetNumber) -> list[Fact]:
    entity, sheet, seen = _target(draft, effect.entity_id)
    if effect.key not in sheet.numbers:
        held = ", ".join(sorted(sheet.numbers)) or "(none)"
        raise ValueError(f"{entity.name} has no number {effect.key!r}. Their numbers are: {held}")
    before = sheet.numbers[effect.key]
    sheet.numbers[effect.key] = effect.value
    trace = f"{entity.name} {effect.key}: {before} -> {effect.value}"
    data = {"key": effect.key, "before": before, "after": effect.value}
    return [*seen, entity_fact(entity, "number_set", trace, data, narrate=False)]


def _changed(entity: Entity, key: str, counter: Counter, delta: int, reason: str) -> Fact:
    data = {"counter": key, "delta": delta, "current": counter.current, "maximum": counter.maximum}
    trace = f"{reason}: {entity.name} {key} {delta:+d} -> {pool(counter)}"
    return entity_fact(entity, "counter_changed", trace, data)
