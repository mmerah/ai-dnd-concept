"""The Director's closed, canon-referencing action vocabulary: the building blocks a turn's
mechanics are assembled from. Each action documents and validates itself, independent of how they
are grouped — which is why the vocabulary is its own module. Consequences form a recursive tree:
`roll_check` nests its branches, `roll_dice` binds a value later consequences reference."""

from collections.abc import Sequence
from typing import Annotated, ClassVar, Literal, get_args

from pydantic import Field

from ...utils.dice import DiceExpr
from .base import ABILITIES, Ability, EntityId, Frozen, Kind

# A canon reference is an id paired with the kind it must be; `None` means any kind (only
# `discover` may reveal anything). Each consequence answers for its own references, so adding one
# never needs a matching edit to a separate validation table.
CanonRef = tuple[EntityId, Kind | None]

# Canon and improvised items are separate variants so the model cannot express a contradictory
# pair. Every canon reference is an id: canonicalization (id -> name) is the resolver's job, never
# the model's. Only items may be improvised — a place the player stands in must exist in canon.


class Ref(Frozen):
    """A value read from a name a prior RollDice bound this turn."""

    ref: str = Field(description="Name of a value bound earlier this turn by `roll_dice`.")


# A literal magnitude, or a value a prior `roll_dice` bound. A Ref is always a positive roll, so a
# damage/heal sign lives in the verb, never the value.
Amount = Annotated[int, Field(ge=0)] | Ref


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

    def children(self) -> tuple["Consequence", ...]:
        return ()


class TakeItem(Frozen):
    """The player picks up a canon item that is here with them."""

    GUIDANCE: ClassVar[str] = """Use when the player takes an item that already exists in canon \
and is at their location; it is revealed first if it was hidden.
Example: they pocket the `vault_map` lying here -> `take_item` with item_id `vault_map`."""

    action: Literal["take_item"] = "take_item"
    item_id: EntityId = Field(description="Id of a canon `item` at the player's location.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.item_id, "item"),)

    def children(self) -> tuple["Consequence", ...]:
        return ()


class DropItem(Frozen):
    """The player drops a held item at their current location."""

    GUIDANCE: ClassVar[str] = """Use when the player puts down or discards an item they carry; it \
comes to rest where they stand.
Example: they set the `vault_map` on the desk -> `drop_item` with item_id `vault_map`."""

    action: Literal["drop_item"] = "drop_item"
    item_id: EntityId = Field(description="Id of a canon `item` the player is carrying.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.item_id, "item"),)

    def children(self) -> tuple["Consequence", ...]:
        return ()


class GiveItem(Frozen):
    """The player hands a held item to another actor who is here."""

    GUIDANCE: ClassVar[str] = """Use when the player gives a carried item to someone at their \
location; the item moves into that actor's inventory.
Example: they hand the `vault_map` to Mara -> `give_item` with item_id `vault_map`, actor_id \
`mara`."""

    action: Literal["give_item"] = "give_item"
    item_id: EntityId = Field(description="Id of a canon `item` the player is carrying.")
    actor_id: EntityId = Field(
        description="Id of the `actor` receiving it, at the player's location."
    )

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ((self.item_id, "item"), (self.actor_id, "actor"))

    def children(self) -> tuple["Consequence", ...]:
        return ()


class GainImprovisedItem(Frozen):
    """The player picks up a minor item that has no canon entry."""

    # Resolution promotes this to a canon item so an inventory always holds real ids, not free text.
    GUIDANCE: ClassVar[str] = """Use only for incidental things no entity backs and none should \
— not worth making canon. Write the item out as free text.
Example: they scoop up loose gravel -> `gain_improvised_item` with item_name 'a handful of \
gravel'."""

    action: Literal["gain_improvised_item"] = "gain_improvised_item"
    item_name: str = Field(description="The item written out, e.g. 'a rusty spoon'.")

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()

    def children(self) -> tuple["Consequence", ...]:
        return ()


class Damage(Frozen):
    """Reduce the character's hit points by an amount, literal or rolled."""

    GUIDANCE: ClassVar[str] = """Use when the character takes damage. `amount` is either a number \
or a reference to a value a prior `roll_dice` bound.
Example: a trap catches them -> `damage` with amount 4. Or after `roll_dice` bound `dmg`: \
`damage` with amount {"ref": "dmg"}."""

    action: Literal["damage"] = "damage"
    amount: Amount = Field(description='Hit points lost: a number >= 0, or {"ref": name}.')

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()

    def children(self) -> tuple["Consequence", ...]:
        return ()


class Heal(Frozen):
    """Restore the character's hit points by an amount, literal or rolled."""

    GUIDANCE: ClassVar[str] = """Use when the character is healed. `amount` is a number or a \
reference to a bound roll. Example: a poultice -> `heal` with amount 5."""

    action: Literal["heal"] = "heal"
    amount: Amount = Field(description='Hit points restored: a number >= 0, or {"ref": name}.')

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()

    def children(self) -> tuple["Consequence", ...]:
        return ()


class Move(Frozen):
    """Move an actor to a location: the player by default, or another actor you name."""

    GUIDANCE: ClassVar[str] = """Use when the player (or an actor you name in `actor_id`) goes \
somewhere that exists in canon, including somewhere not discovered yet — the player arriving, or \
someone arriving where the player is, reveals it. If they head somewhere the world does not have, \
leave `move` out and let the narration take them toward it; the place becomes canon and you can \
move them there on a later turn.
Example: "I go down to the vault" and `vault` is in your lists -> `move` with location_id `vault`. \
Mara walks off to the cloister -> `move` location_id `cloister`, actor_id `mara`."""

    action: Literal["move"] = "move"
    location_id: EntityId = Field(description="Id of a canon entity whose kind is `location`.")
    actor_id: EntityId | None = Field(
        default=None, description="Id of the `actor` to move; omit to move the player."
    )

    def canon_refs(self) -> tuple[CanonRef, ...]:
        base: tuple[CanonRef, ...] = ((self.location_id, "location"),)
        return base if self.actor_id is None else (*base, (self.actor_id, "actor"))

    def children(self) -> tuple["Consequence", ...]:
        return ()


class RollCheck(Frozen):
    """Roll an ability check against a DC, then apply the branch that the result selects."""

    GUIDANCE: ClassVar[str] = """Use when an action can fail. Put what passing does in \
`on_success`, what failing does in `on_failure`; either may be empty."""

    action: Literal["roll_check"] = "roll_check"
    ability: Ability = Field(description=f"One of: {', '.join(ABILITIES)}.")
    dc: int = Field(description="5 easy, 10 moderate, 15 hard, 20 very hard.")
    on_success: list["Consequence"] = Field(
        default_factory=list, description="Applied iff the check passes."
    )
    on_failure: list["Consequence"] = Field(
        default_factory=list, description="Applied iff the check fails."
    )

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()

    def children(self) -> tuple["Consequence", ...]:
        return (*self.on_success, *self.on_failure)


class RollDice(Frozen):
    """Roll dice, bind the total to a name, then apply consequences that may reference it."""

    GUIDANCE: ClassVar[str] = """Use to roll damage or any random amount. `dice` is like '1d8' or \
'2d6+3'. `bind` names the total so a following `damage`/`heal` can use it via {"ref": name}.
Example: `roll_dice` dice '1d8' bind 'dmg', then in `then` a `damage` with amount {"ref": \
"dmg"}."""

    action: Literal["roll_dice"] = "roll_dice"
    dice: DiceExpr = Field(description="e.g. '1d8', '2d6 + 3', '4d6 + 4'.")
    bind: str = Field(description='Name to store the total under, for a later {"ref": name}.')
    then: list["Consequence"] = Field(
        default_factory=list, description="Consequences that may reference `bind`."
    )

    def canon_refs(self) -> tuple[CanonRef, ...]:
        return ()

    def children(self) -> tuple["Consequence", ...]:
        return tuple(self.then)


Consequence = Annotated[
    Discover
    | TakeItem
    | DropItem
    | GiveItem
    | GainImprovisedItem
    | Damage
    | Heal
    | Move
    | RollCheck
    | RollDice,
    Field(discriminator="action"),
]

# One source for the union's members, so the Director's menu and any future walker stay in step
# with the type. `get_args` erases to `Any`, but the union guarantees these are the member classes.
CONSEQUENCE_TYPES: tuple[type[Consequence], ...] = get_args(get_args(Consequence)[0])

# RollCheck/RollDice reference "Consequence" before the alias exists; bind the forward ref now.
RollCheck.model_rebuild()
RollDice.model_rebuild()


def all_canon_refs(consequences: Sequence["Consequence"]) -> list[CanonRef]:
    """Every canon ref in a consequence tree, including nested branches."""
    out: list[CanonRef] = []
    for c in consequences:
        out.extend(c.canon_refs())
        out.extend(all_canon_refs(c.children()))
    return out
