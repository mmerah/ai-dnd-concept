"""The Director's proposal: a check and a closed, canon-referencing consequence vocabulary."""

from typing import Annotated, Literal

from pydantic import Field

from .base import Ability, EntityId, Frozen

# Canon vs loose items are separate variants so the model cannot express a contradictory pair, and
# so canonicalization (id -> name) is the resolver's job, never the model's.


class Discover(Frozen):
    action: Literal["discover"] = "discover"
    entity_id: EntityId


class GainCanonItem(Frozen):
    action: Literal["gain_canon_item"] = "gain_canon_item"
    entity_id: EntityId


class GainLooseItem(Frozen):
    action: Literal["gain_loose_item"] = "gain_loose_item"
    item: str


class LoseCanonItem(Frozen):
    action: Literal["lose_canon_item"] = "lose_canon_item"
    entity_id: EntityId


class LoseLooseItem(Frozen):
    action: Literal["lose_loose_item"] = "lose_loose_item"
    item: str


class ModifyHp(Frozen):
    action: Literal["modify_hp"] = "modify_hp"
    delta: int


class Move(Frozen):
    action: Literal["move"] = "move"
    location: str


Consequence = Annotated[
    Discover | GainCanonItem | GainLooseItem | LoseCanonItem | LoseLooseItem | ModifyHp | Move,
    Field(discriminator="action"),
]


class Check(Frozen):
    ability: Ability
    dc: int


class Plan(Frozen):
    check: Check | None = None
    unconditional: list[Consequence] = Field(default_factory=list)  # always applied
    on_success: list[Consequence] = Field(default_factory=list)  # applied iff the check passes
    on_failure: list[Consequence] = Field(default_factory=list)  # applied iff the check fails


class Direction(Frozen):
    """Director output. Only `intent`/`tone`/speaker reach the Narrator, which treats `intent` as
    what was attempted, not what happened; `plan` is resolved in Python."""

    intent: str
    tone: str
    speaker_id: EntityId | None = None
    plan: Plan = Field(default_factory=Plan)
