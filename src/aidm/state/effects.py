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
TieKind = Annotated[Slug, Field(description="Exact kind of the tie, such as `connected`.")]
TieSource = Annotated[EntityId, Field(description="Exact id of the tie's source entity.")]
TieTarget = Annotated[EntityId, Field(description="Exact id of the tie's target entity.")]


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
    maximum: int | None = Field(
        default=None, description="A new upper bound for the pool. Advancement only."
    )
    why: Why = ""


class SpendCounter(Frozen):
    """Pay from a counter, which refuses outright when the pool cannot cover it."""

    op: Literal["spend-counter"] = "spend-counter"
    entity_id: TargetId
    counter: CounterKey
    amount: int = Field(ge=1, description="How much of the pool is spent.")
    why: Why = ""


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


class AddTag(Frozen):
    """Put a lasting condition, edge, or burden on an entity. The sheet shows the id written
    out: `battle-worn` appears as Battle Worn."""

    op: Literal["add-tag"] = "add-tag"
    entity_id: TargetId
    tag_id: Slug = Field(description="Stable slug for the tag, such as `poisoned`.")
    text: str = Field(
        default="", description="The constraint or benefit it puts on the entity, in prose."
    )
    why: Why = ""


class RemoveTag(Frozen):
    """Lift a tag an entity carries, when the fiction ends it."""

    op: Literal["remove-tag"] = "remove-tag"
    entity_id: TargetId
    tag_id: Slug = Field(description="Exact id of a tag the entity carries.")
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


class AddRelation(Frozen):
    """Record a lasting tie between two entities that is not containment: carrying an item or
    standing somewhere are moves, not relations."""

    op: Literal["add-relation"] = "add-relation"
    kind: Slug = Field(
        description="What the tie is: `connected` joins two locations the player can walk "
        "between, `party-member` puts an actor here into the player's party (source is the "
        "actor, target is `player`)."
    )
    source: TieSource
    target: TieTarget
    why: Why = ""


class RemoveRelation(Frozen):
    """Break a lasting tie that `add-relation` recorded."""

    op: Literal["remove-relation"] = "remove-relation"
    kind: TieKind
    source: TieSource
    target: TieTarget
    why: Why = ""


class TagRelation(Frozen):
    """Mark a tie — most often a connection — as blocked, such as `locked`, until
    `untag-relation` lifts it again."""

    op: Literal["tag-relation"] = "tag-relation"
    kind: TieKind
    source: TieSource
    target: TieTarget
    tag: Slug = Field(description="Stable slug for the tag, such as `locked`.")
    why: Why = ""


class UntagRelation(Frozen):
    """Lift a tag a tie carries, when the fiction ends it."""

    op: Literal["untag-relation"] = "untag-relation"
    kind: TieKind
    source: TieSource
    target: TieTarget
    tag: Slug = Field(description="Exact id of a tag the tie carries.")
    why: Why = ""


class RevealRelation(Frozen):
    """Show the player a way through they did not know about: the connection equivalent of
    `reveal`. Write this before moving the player through a passage they have not found yet."""

    op: Literal["reveal-relation"] = "reveal-relation"
    kind: TieKind
    source: TieSource
    target: TieTarget


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
    | MoveActor
    | MoveItem
    | GainImprovisedItem
    | AdjustCounter
    | SpendCounter
    | GrantCounter
    | Refill
    | AddTag
    | RemoveTag
    | SetNote
    | SetNumber
    | AddRef
    | AddRelation
    | RemoveRelation
    | TagRelation
    | UntagRelation
    | RevealRelation
    | AdvanceThread,
    Field(discriminator="op"),
]

# What the Director writes: only the changes the fiction alone decides. A note, a lasting number,
# and locking a way through are an engine program's, advancement's, or the scenario author's.
type TurnEffect = Annotated[
    Reveal
    | MoveActor
    | MoveItem
    | GainImprovisedItem
    | AdjustCounter
    | SpendCounter
    | AddTag
    | RemoveTag
    | AddRelation
    | RemoveRelation
    | UntagRelation
    | RevealRelation
    | AdvanceThread,
    Field(discriminator="op"),
]

type SheetEffect = Annotated[
    AdjustCounter | SpendCounter | GrantCounter | AddTag | RemoveTag | SetNote | SetNumber | AddRef,
    Field(discriminator="op"),
]


WORLD_OPS = (
    Reveal,
    MoveActor,
    MoveItem,
    GainImprovisedItem,
    AddRelation,
    RemoveRelation,
    TagRelation,
    UntagRelation,
    RevealRelation,
    AdvanceThread,
)


class SheetDelta(Frozen):
    """What advancement writes onto the player's sheet, each change carrying its reason."""

    changes: tuple[SheetEffect, ...] = ()


def turn_effect_ops() -> frozenset[str]:
    union, _ = get_args(TurnEffect.__value__)
    return frozenset(member.model_fields["op"].default for member in get_args(union))
