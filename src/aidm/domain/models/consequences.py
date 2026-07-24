"""The Director's closed, canon-referencing action vocabulary: the building blocks a turn's
`Mechanics` are assembled from. Each action documents and validates itself, independent of how
they are grouped — which is why the vocabulary is its own module."""

from typing import Annotated, ClassVar, Literal, get_args

from pydantic import Field

from .base import EntityId, Frozen, Kind

# A canon reference is an id paired with the kind it must be; `None` means any kind (only
# `discover` may reveal anything). Each consequence answers for its own references, so adding one
# never needs a matching edit to a separate validation table.
CanonRef = tuple[EntityId, Kind | None]

# Canon and improvised items are separate variants so the model cannot express a contradictory
# pair. Every canon reference is an id: canonicalization (id -> name) is the resolver's job, never
# the model's. Only items may be improvised — a place the player stands in must exist in canon.


class Discover(Frozen):
    """Reveal something that already exists to the player."""

    GUIDANCE: ClassVar[str] = """Use when the player's action brings an existing but unrevealed \
entity into view — they notice it, are told of it, or reach it. May reveal any kind.
Example: the player studies a shelf and `ledger` is in your unrevealed list -> `discover` with \
entity_id `ledger`."""

    action: Literal["discover"] = "discover"
    entity_id: EntityId = Field(description="Id of any canon entity, of any kind.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.entity_id, None),)  # discover alone may reveal any kind


class GainItem(Frozen):
    """Put a canon item into the character's inventory."""

    GUIDANCE: ClassVar[str] = """Use when the player takes or is given an item that already \
exists in canon; it is revealed first if it was hidden.
Example: they pocket the `vault_map` from your lists -> `gain_item` with item_id `vault_map`."""

    action: Literal["gain_item"] = "gain_item"
    item_id: EntityId = Field(description="Id of a canon entity whose kind is `item`.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.item_id, "item"),)


class LoseItem(Frozen):
    """Take a canon item out of the character's inventory."""

    GUIDANCE: ClassVar[str] = """Use when a canon item leaves the character — dropped, given \
away, spent or destroyed.
Example: they hand the `vault_map` to an ally -> `lose_item` with item_id `vault_map`."""

    action: Literal["lose_item"] = "lose_item"
    item_id: EntityId = Field(description="Id of a canon entity whose kind is `item`.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.item_id, "item"),)


class GainImprovisedItem(Frozen):
    """Put a minor item that has no canon entry into the character's inventory."""

    GUIDANCE: ClassVar[str] = """Use only for incidental things no entity backs and none should \
— not worth making canon. Write the item out as free text.
Example: they scoop up loose gravel -> `gain_improvised_item` with item_name 'a handful of \
gravel'."""

    action: Literal["gain_improvised_item"] = "gain_improvised_item"
    item_name: str = Field(description="The item written out, e.g. 'a rusty spoon'.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()


class LoseImprovisedItem(Frozen):
    """Take a minor item that has no canon entry out of the character's inventory."""

    GUIDANCE: ClassVar[str] = """Use to remove an improvised item, spelled exactly as it is held.
Example: they toss away 'a handful of gravel' -> `lose_improvised_item` with that item_name."""

    action: Literal["lose_improvised_item"] = "lose_improvised_item"
    item_name: str = Field(description="The item written out, exactly as it is held.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()


class ModifyHp(Frozen):
    """Change the character's hit points."""

    GUIDANCE: ClassVar[str] = """Use when the character takes damage or is healed. Negative for \
damage, positive for healing.
Example: a trap catches them -> `modify_hp` with delta -4."""

    action: Literal["modify_hp"] = "modify_hp"
    delta: int = Field(description="Hit points to add; negative for damage.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()


class Move(Frozen):
    """Move the character to a location."""

    GUIDANCE: ClassVar[str] = """Use when the player goes somewhere that exists in canon, \
including somewhere they have not discovered yet — arriving reveals it. If they head somewhere \
the world does not contain, leave `move` out and let the narration take them toward it; the place \
becomes canon and you can move them there on a later turn.
Example: the player says "I go down to the vault" and `vault` is in your lists -> `move` with \
location_id `vault`."""

    action: Literal["move"] = "move"
    location_id: EntityId = Field(description="Id of a canon entity whose kind is `location`.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.location_id, "location"),)


Consequence = Annotated[
    Discover
    | GainItem
    | LoseItem
    | GainImprovisedItem
    | LoseImprovisedItem
    | ModifyHp
    | Move,
    Field(discriminator="action"),
]

# One source for the union's members, so the Director's menu and any future walker stay in step
# with the type. `get_args` erases to `Any`, but the union guarantees these are the member classes.
CONSEQUENCE_TYPES: tuple[type[Consequence], ...] = get_args(get_args(Consequence)[0])
