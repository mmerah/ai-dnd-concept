from typing import Annotated, Literal, Self, get_args

from pydantic import Field, model_validator

from .base import EntityId, Frozen, Slug, ThreadStatus
from .packs import ContentRef

TargetId = Annotated[
    EntityId,
    Field(description="Exact id of the entity affected; an actor must be here with the player."),
]
CounterKey = Annotated[
    Slug, Field(description="Exact key of one of that entity's counters, as its sheet spells it.")
]
Why = Annotated[
    str, Field(description="One short sentence saying what causes this change, for the player.")
]


class Reveal(Frozen):
    """Reveal an entity that exists but the player does not know yet: they notice it, are told of
    it, or reach it. Prefer this over inventing a replacement."""

    op: Literal["reveal"] = "reveal"
    entity_id: EntityId = Field(description="Exact id of the unrevealed canon entity.")


class Move(Frozen):
    """Move an actor who actually changes location, or one item within the player's reach: picked
    up, set down here, or handed to an actor here. Moving the player to an unrevealed location
    reveals it."""

    op: Literal["move"] = "move"
    entity_id: EntityId | None = Field(
        default=None,
        description="Exact id of the actor or item that moves; null moves the player. An item "
        "must be one the player carries, or one loose at their location.",
    )
    to_id: EntityId | None = Field(
        default=None,
        description="Exact id of where it goes: for an actor the location they enter; for an item "
        "an actor here with the player, or the player's own location to set it down. An actor "
        "always names one; null hands the item to the player.",
    )


class GainImprovisedItem(Frozen):
    """Give the player an ordinary incidental object that is not in canon and is not worth a canon
    entry of its own. Never a substitute for an item that already exists."""

    op: Literal["gain-improvised-item"] = "gain-improvised-item"
    item_name: str = Field(
        min_length=1, description="The object written out, such as 'a handful of gravel'."
    )


class CounterChange(Frozen):
    """Move a counter: `adjust` shifts it by a delta, clamped to the counter's own bounds;
    `spend` pays a cost from it and refuses when the pool cannot cover it."""

    op: Literal["counter-change"] = "counter-change"
    mode: Literal["adjust", "spend"] = Field(
        description="`adjust` moves the pool, `spend` pays from it and can refuse."
    )
    entity_id: TargetId
    counter: CounterKey
    amount: int = Field(
        description="For `adjust`, how much the pool moves: negative to reduce. For `spend`, how "
        "much of the pool is paid, always positive."
    )
    maximum: int | None = Field(
        default=None, description="A new upper bound for the pool. Adjust, and advancement only."
    )
    why: Why = ""

    @model_validator(mode="after")
    def _spend_pays(self) -> Self:
        """A negative spend would refill the pool it claims to pay from."""
        if self.mode == "spend":
            if self.amount < 1:
                raise ValueError("spend pays a positive amount; use adjust to raise a pool")
            if self.maximum is not None:
                raise ValueError("only adjust changes a maximum")
        return self


class GrantCounter(Frozen):
    """Give a sheet a pool it does not have yet. Advancement only: a turn changes pools, never
    invents them."""

    op: Literal["grant-counter"] = "grant-counter"
    entity_id: TargetId
    counter: CounterKey
    current: int
    maximum: int | None = Field(default=None, description="Omit for an unbounded pool.")
    minimum: int = 0
    recharge: str | None = Field(default=None, description="A recharge label of this engine.")
    why: Why = ""


class Refill(Frozen):
    """Refill every counter whose recharge label the rest covers. Engine resolvers only: the
    Director plans a rest, never the refill itself."""

    op: Literal["refill"] = "refill"
    entity_id: TargetId
    label: str = Field(description="Which rest was taken; it names the fact.")
    recharges: tuple[str, ...] = Field(min_length=1, description="The recharge labels it refills.")


class TagChange(Frozen):
    """Put a lasting condition, edge, or burden on an entity, or lift one the fiction ends. The
    sheet shows the id written out: `battle-worn` appears as Battle Worn."""

    op: Literal["tag-change"] = "tag-change"
    mode: Literal["add", "remove"] = Field(
        description="`add` puts the tag on, `remove` lifts one the entity carries."
    )
    entity_id: TargetId
    tag_id: Slug = Field(
        description="Stable slug for the tag, such as `poisoned`; to remove, the exact id of a "
        "tag the entity carries."
    )
    text: str = Field(
        default="",
        description="The constraint or benefit it puts on the entity, in prose. Adding only.",
    )
    why: Why = ""


class SetNote(Frozen):
    """Write freeform bookkeeping the fiction needs remembered and no counter or tag holds, such as
    what a caster concentrates on. Writing a key again replaces what it held."""

    op: Literal["set-note"] = "set-note"
    entity_id: TargetId
    key: Slug = Field(description="What the note is about, such as `concentration`.")
    text: str = Field(description="The note; empty clears whatever the key held.")
    why: Why = ""


class SetNumber(Frozen):
    """Set a number the fiction has lastingly changed — armour worn, a permanent blessing. Never
    for this turn's outcome: pools that go up and down are counters."""

    op: Literal["set-number"] = "set-number"
    entity_id: TargetId
    key: Slug = Field(description="Exact key of a number already on that sheet.")
    value: int = Field(description="What the number becomes.")
    why: Why = ""


class AddRef(Frozen):
    """Put a content record on a sheet. Advancement only: a turn never grants content."""

    op: Literal["add-ref"] = "add-ref"
    entity_id: TargetId
    ref: ContentRef = Field(description="One of the picks the offer allows.")
    why: Why = ""


class RelationChange(Frozen):
    """Record, break, unblock, or reveal a lasting tie between two entities. Containment is not a
    tie: carrying an item or standing somewhere are moves. `reveal` shows the player a way through
    they did not know about; write it before moving them through a passage they have not found.
    `untag` lifts a block such as `locked` when the fiction opens it."""

    op: Literal["relation-change"] = "relation-change"
    mode: Literal["add", "remove", "untag", "reveal"] = Field(
        description="What happens to the tie: `add` records it, `remove` breaks it, `untag` lifts "
        "a tag it carries, `reveal` shows it to the player."
    )
    kind: Slug = Field(
        description="What the tie is: `connected` joins two locations the player can walk "
        "between, `party-member` puts an actor here into the player's party (source is the "
        "actor, target is `player`)."
    )
    source: EntityId = Field(description="Exact id of the tie's source entity.")
    target: EntityId = Field(description="Exact id of the tie's target entity.")
    tag: Slug | None = Field(
        default=None,
        description="For `untag` only: the exact id of a tag the tie carries, such as `locked`.",
    )
    why: Why = ""

    @model_validator(mode="after")
    def _tag_belongs_to_untag(self) -> Self:
        if (self.tag is None) != (self.mode != "untag"):
            raise ValueError("`tag` names the tag `untag` lifts, and belongs to no other mode")
        return self


class AdvanceThread(Frozen):
    """Move a storyline the scenario is tracking: where it stands now, or that it is over."""

    op: Literal["advance-thread"] = "advance-thread"
    thread_id: Slug = Field(description="Exact id of one thread in ACTIVE THREADS.")
    status: ThreadStatus | None = Field(
        default=None, description="Where the thread now stands, or null to leave it as it is."
    )
    stage: Slug | None = Field(
        default=None,
        description="Stable slug for the point it has reached, or null to leave it as it is.",
    )
    why: Why = ""

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if self.status is None and self.stage is None:
            raise ValueError("advance-thread moves a thread's status, its stage, or both")
        return self


type Effect = Annotated[
    Reveal
    | Move
    | GainImprovisedItem
    | CounterChange
    | GrantCounter
    | Refill
    | TagChange
    | SetNote
    | SetNumber
    | AddRef
    | RelationChange
    | AdvanceThread,
    Field(discriminator="op"),
]

# What the Director writes: only the changes the fiction alone decides. A note, a lasting number,
# and granting a pool are an engine program's, advancement's, or the scenario author's.
type TurnEffect = Annotated[
    Reveal | Move | GainImprovisedItem | CounterChange | TagChange | RelationChange | AdvanceThread,
    Field(discriminator="op"),
]

type SheetEffect = Annotated[
    CounterChange | GrantCounter | TagChange | SetNote | SetNumber | AddRef,
    Field(discriminator="op"),
]


WORLD_OPS = (Reveal, Move, GainImprovisedItem, RelationChange, AdvanceThread)


class SheetDelta(Frozen):
    """What advancement writes onto the player's sheet, each change carrying its reason."""

    changes: tuple[SheetEffect, ...] = ()


def effect_key(effect: Effect) -> str:
    """An op, or an op and the mode it is in: what one worked example teaches."""
    mode = effect.model_dump().get("mode")
    return f"{effect.op}/{mode}" if mode else effect.op


def turn_effect_keys() -> frozenset[str]:
    union, _ = get_args(TurnEffect.__value__)
    keys: set[str] = set()
    for member in get_args(union):
        op = member.model_fields["op"].default
        mode = member.model_fields.get("mode")
        if mode is None:
            keys.add(op)
        else:
            keys.update(f"{op}/{value}" for value in get_args(mode.annotation))
    return frozenset(keys)
