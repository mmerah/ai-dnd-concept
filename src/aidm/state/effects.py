from typing import Annotated, Literal, Self, get_args

from pydantic import Field, model_validator

from .base import EntityId, Frozen, Slug, ThreadStatus

TargetId = Annotated[
    EntityId,
    Field(description="Exact id of the entity affected; an actor must be here with the player."),
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


class TraitChange(Frozen):
    """Put a lasting condition, edge, or burden on an entity, or lift one the fiction ends. The
    trait shows the id written out: `battle-worn` appears as Battle Worn."""

    op: Literal["trait-change"] = "trait-change"
    mode: Literal["add", "remove"] = Field(
        description="`add` puts the trait on, `remove` lifts one the entity carries."
    )
    entity_id: TargetId
    trait_id: Slug = Field(
        description="Stable slug for the trait, such as `poisoned`; to remove, the exact id of a "
        "trait the entity carries."
    )
    text: str = Field(
        default="",
        description="The constraint or benefit it puts on the entity, in prose. Adding only.",
    )
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


# Everything core can write: fiction, and nothing an engine has to interpret. An engine's own
# effect union is `WorldOp | <its mechanical ops>` under the same discriminator.
type WorldOp = Reveal | Move | GainImprovisedItem | TraitChange | RelationChange | AdvanceThread
type WorldEffect = Annotated[WorldOp, Field(discriminator="op")]


def effect_key(effect: Frozen) -> str:
    """An op, or an op and the mode it is in: what one worked example teaches."""
    dumped = effect.model_dump()
    mode = dumped.get("mode")
    return f"{dumped['op']}/{mode}" if mode else str(dumped["op"])


def effect_keys(union: object) -> frozenset[str]:
    """Every key an effect union can produce, so a worked example can be demanded per mode."""
    members, _ = get_args(union)
    keys: set[str] = set()
    for member in get_args(members):
        op = member.model_fields["op"].default
        mode = member.model_fields.get("mode")
        if mode is None:
            keys.add(op)
        else:
            keys.update(f"{op}/{value}" for value in get_args(mode.annotation))
    return frozenset(keys)
