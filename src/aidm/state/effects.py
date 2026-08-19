from typing import Annotated, Literal, Self, TypeIs

from pydantic import Field, model_validator

from .base import EntityId, Frozen, Slug, ThreadStatus

TargetId = Annotated[
    EntityId,
    Field(description="Exact id of the entity affected; an actor must be here with the player."),
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
    entity_id: EntityId = Field(
        description="Exact id of the actor or item that moves; `player` is the played character. "
        "An item must be one the player carries, or one loose at their location.",
    )
    to_id: EntityId = Field(
        description="Exact id of where it goes: for an actor the location they enter; for an item, "
        "`player` to pick it up, an actor here with the player to hand it over, or the player's "
        "own location to set it down.",
    )


class GainImprovisedItem(Frozen):
    """Give the player an ordinary incidental object that is not in canon and is not worth a canon
    entry of its own. Never a substitute for an item that already exists."""

    op: Literal["gain-improvised-item"] = "gain-improvised-item"
    item_name: str = Field(
        min_length=1, description="The object written out, such as 'a handful of gravel'."
    )


class TraitChange(Frozen):
    """Put a lasting condition, skill, or frailty on an entity, or lift one the fiction ends. The
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


class RelationChange(Frozen):
    """Record, break, unblock, or reveal a lasting tie between two entities. Containment is not a
    tie: carrying an item or standing somewhere are moves. `reveal` shows the player a way through
    they did not know about; write it before moving them through a passage they have not found.
    `unlock` opens a locked way when the fiction opens it."""

    op: Literal["relation-change"] = "relation-change"
    mode: Literal["add", "remove", "unlock", "reveal"] = Field(
        description="What happens to the tie: `add` records it, `remove` breaks it, `unlock` "
        "opens a way that was locked, `reveal` shows it to the player."
    )
    kind: Slug = Field(
        description="What the tie is: `connected` joins two locations the player can walk "
        "between, `party-member` puts an actor here into the player's party (source is the "
        "actor, target is `player`)."
    )
    source: EntityId = Field(description="Exact id of the tie's source entity.")
    target: EntityId = Field(description="Exact id of the tie's target entity.")


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
    tick: int = Field(
        default=0,
        description="How many segments this fills on the thread's clock, when it has one.",
    )

    @model_validator(mode="after")
    def _moves_something(self) -> Self:
        if self.tick < 0:
            raise ValueError("a tick fills a clock; it never runs one backwards")
        if self.status is None and self.stage is None and not self.tick:
            raise ValueError("advance-thread moves a thread's status, its stage, or its clock")
        return self


# Everything core can write: fiction, and nothing an engine has to interpret. An engine's own
# effect union is `WorldOp | <its mechanical ops>` under the same discriminator.
type WorldOp = Reveal | Move | GainImprovisedItem | TraitChange | RelationChange | AdvanceThread
type WorldEffect = Annotated[WorldOp, Field(discriminator="op")]


def is_world_op(effect: Frozen) -> TypeIs[WorldOp]:
    # Kept directly under the alias, so a new op is added to both or neither.
    return isinstance(
        effect, (Reveal, Move, GainImprovisedItem, TraitChange, RelationChange, AdvanceThread)
    )
