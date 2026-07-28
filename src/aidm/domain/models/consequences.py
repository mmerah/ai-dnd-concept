from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal, get_args

from pydantic import Field

from ...content.vocabulary import CONDITION_NAMES, ConditionName
from ...utils.dice import SelfContainedDice
from ...utils.models import ABILITIES, Ability, Frozen, Kind
from .base import PLAYER_ID, EntityId


@dataclass(frozen=True, slots=True)
class References:
    kind: Kind | None
    present: bool = False


CanonRef = tuple[EntityId, References]

# The consuming action owns the sign, so magnitudes stay non-negative.
Magnitude = SelfContainedDice | Annotated[int, Field(ge=0, strict=True)]


class Action(Frozen):
    def check(self) -> str | None:
        return None


class Discover(Action):
    """Reveal something that already exists to the player."""

    GUIDANCE: ClassVar[str] = """Use when the player's action brings an existing but unrevealed \
entity into view — they notice it, are told of it, or reach it. May reveal any kind.
Example: the player studies a shelf and `ledger` is in your unrevealed list -> `discover` with \
entity_id `ledger`."""

    action: Literal["discover"] = "discover"
    entity_id: Annotated[EntityId, References(None)] = Field(
        description="Id of any canon entity, of any kind."
    )


class TakeItem(Action):
    """The player picks up a canon item that is here with them."""

    GUIDANCE: ClassVar[str] = """Use when the player takes an item that already exists in canon \
and is at their location; it is revealed first if it was hidden.
Example: they pocket the `vault_map` lying here -> `take_item` with item_id `vault_map`."""

    action: Literal["take_item"] = "take_item"
    item_id: Annotated[EntityId, References("item")] = Field(
        description="Id of a canon `item` at the player's location."
    )


class DropItem(Action):
    """The player drops a held item at their current location."""

    GUIDANCE: ClassVar[str] = """Use when the player puts down or discards an item they carry; it \
comes to rest where they stand.
Example: they set the `vault_map` on the desk -> `drop_item` with item_id `vault_map`."""

    action: Literal["drop_item"] = "drop_item"
    item_id: Annotated[EntityId, References("item")] = Field(
        description="Id of a canon `item` the player is carrying."
    )


class GiveItem(Action):
    """The player hands a held item to another actor who is here."""

    GUIDANCE: ClassVar[str] = """Use when the player gives a carried item to someone at their \
location; the item moves into that actor's inventory.
Example: they hand the `vault_map` to Mara -> `give_item` with item_id `vault_map`, actor_id \
`mara`."""

    action: Literal["give_item"] = "give_item"
    item_id: Annotated[EntityId, References("item")] = Field(
        description="Id of a canon `item` the player is carrying."
    )
    actor_id: Annotated[EntityId, References("actor", present=True)] = Field(
        description="Id of the `actor` receiving it, at the player's location."
    )

    def check(self) -> str | None:
        if self.actor_id == PLAYER_ID:
            return "give_item must name another actor: the player already holds the item"
        return None


class GainImprovisedItem(Action):
    """The player picks up a minor item that has no canon entry."""

    GUIDANCE: ClassVar[str] = """Use only for incidental things no entity backs and none should \
— not worth making canon. Write the item out as free text.
Example: they scoop up loose gravel -> `gain_improvised_item` with item_name 'a handful of \
gravel'."""

    action: Literal["gain_improvised_item"] = "gain_improvised_item"
    item_name: str = Field(description="The item written out, e.g. 'a rusty spoon'.")


class Damage(Action):
    """Reduce an actor's hit points by dice you roll, or by a flat amount."""

    GUIDANCE: ClassVar[str] = """Use when someone here takes damage. Prefer dice — '1d6', \
'2d6 + 3' — and let them fall; a flat number is for harm with nothing left to chance. Whether a \
blow lands is never yours to decide: put the damage in a `roll_check` branch.
Example: a trap catches the player -> `damage` with amount '2d4'. Kael swings at Mara -> \
`roll_check` whose on_success is `damage` with amount '1d8', target_id `mara`."""

    action: Literal["damage"] = "damage"
    amount: Magnitude = Field(description="Hit points lost: dice like '2d6', or a number >= 0.")
    target_id: Annotated[EntityId | None, References("actor", present=True)] = Field(
        default=None, description="Id of the `actor` harmed, here with the player; omit for them."
    )


class Heal(Action):
    """Restore an actor's hit points by dice you roll, or by a flat amount."""

    GUIDANCE: ClassVar[str] = """Use when someone here is healed; the same amount and target rules \
as `damage`. Example: a poultice on the player -> `heal` with amount '1d4 + 2'."""

    action: Literal["heal"] = "heal"
    amount: Magnitude = Field(description="Hit points restored: dice like '1d4', or a number >= 0.")
    target_id: Annotated[EntityId | None, References("actor", present=True)] = Field(
        default=None, description="Id of the `actor` healed, here with the player; omit for them."
    )


class ApplyCondition(Action):
    """Put an actor under an SRD condition, or lift one they are already under."""

    GUIDANCE: ClassVar[str] = """Use when someone here is blinded, grappled, frightened, knocked \
prone and so on, and when that ends. A creature immune to the condition is unaffected — you do not \
need to check, the rules do. Whether it takes hold is not yours to decide when it could be \
resisted: put it in a `roll_check` branch.
Example: the player slips on wet stone -> `apply_condition` with condition 'prone'. They stand up \
again -> the same with ends true."""

    action: Literal["apply_condition"] = "apply_condition"
    condition: ConditionName = Field(description=f"One of: {', '.join(CONDITION_NAMES)}.")
    ends: bool = Field(default=False, description="True to lift the condition instead of applying.")
    target_id: Annotated[EntityId | None, References("actor", present=True)] = Field(
        default=None, description="Id of the `actor` affected, here with the player; omit for them."
    )


class Move(Action):
    """Move an actor to a location: the player by default, or another actor you name."""

    GUIDANCE: ClassVar[str] = """Use when the player (or an actor you name in `actor_id`) goes \
somewhere that exists in canon, including somewhere not discovered yet — the player arriving, or \
someone arriving where the player is, reveals it. If they head somewhere the world does not have, \
leave `move` out and let the narration take them toward it; the place becomes canon and you can \
move them there on a later turn.
Example: "I go down to the vault" and `vault` is in your lists -> `move` with location_id `vault`. \
Mara walks off to the cloister -> `move` location_id `cloister`, actor_id `mara`."""

    action: Literal["move"] = "move"
    location_id: Annotated[EntityId, References("location")] = Field(
        description="Id of a canon entity whose kind is `location`."
    )
    actor_id: Annotated[EntityId | None, References("actor")] = Field(
        default=None, description="Id of the `actor` to move; omit to move the player."
    )


class Attack(Action):
    """Strike another actor; the rules determine the hit and damage."""

    GUIDANCE: ClassVar[str] = """Use for a deliberate blow — the player swinging, or someone here \
swinging at them. Name the weapon exactly as you were shown it: one of the attacker's own attacks \
from their stat block, or an item they carry. The to-hit roll, the target's armour and the damage \
are all the rules' business, so there is nothing to wrap in a `roll_check`.
Nobody strikes at themselves, so name at most one of the two ids.
Example: the goblin lunges at the player -> `attack` with attacker_id `goblin`, weapon 'Scimitar'. \
The player swings back -> `attack` with target_id `goblin`, weapon 'a notched longsword'."""

    action: Literal["attack"] = "attack"
    weapon: str = Field(
        description="The attacker's own attack by name, or an item they carry, spelled as shown."
    )
    target_id: Annotated[EntityId | None, References("actor", present=True)] = Field(
        default=None,
        description="Id of the `actor` struck at, here with the player; omit for them.",
    )
    attacker_id: Annotated[EntityId | None, References("actor", present=True)] = Field(
        default=None, description="Id of the `actor` attacking; omit for the player."
    )

    def check(self) -> str | None:
        if (self.attacker_id or PLAYER_ID) == (self.target_id or PLAYER_ID):
            return "attack must name at most one of attacker_id and target_id: they differ"
        return None


class DcRoll(Action):
    """A d20 roll whose result selects one nested branch."""

    ability: Ability = Field(description=f"One of: {', '.join(ABILITIES)}.")
    dc: int = Field(description="5 easy, 10 moderate, 15 hard, 20 very hard.")
    on_success: list["Consequence"] = Field(
        default_factory=list, description="Applied iff the roll succeeds."
    )
    on_failure: list["Consequence"] = Field(
        default_factory=list, description="Applied iff the roll fails."
    )


class RollCheck(DcRoll):
    """Roll the player's ability check against a DC, then apply the branch the result selects."""

    GUIDANCE: ClassVar[str] = """Use when something the player attempts can fail. Put what passing \
does in `on_success`, what failing does in `on_failure`; either may be empty."""

    action: Literal["roll_check"] = "roll_check"


class RollSave(DcRoll):
    """Make an actor resist something aimed at them, then apply the branch the result selects."""

    GUIDANCE: ClassVar[str] = """Use when something is done *to* someone and they may shrug it off \
— a trap's gas, a spell, a shove. The difference from `roll_check` is who rolls and which bonus \
applies; the rules know both.
Example: gas floods the crypt -> `roll_save` ability 'constitution', dc 12, whose on_failure is \
`damage` with amount '2d4'."""

    action: Literal["roll_save"] = "roll_save"
    target_id: Annotated[EntityId | None, References("actor", present=True)] = Field(
        default=None,
        description="Id of the `actor` resisting, here with the player; omit for them.",
    )


Consequence = Annotated[
    Discover
    | TakeItem
    | DropItem
    | GiveItem
    | GainImprovisedItem
    | Damage
    | Heal
    | ApplyCondition
    | Move
    | Attack
    | RollCheck
    | RollSave,
    Field(discriminator="action"),
]

CONSEQUENCE_TYPES: tuple[type[Consequence], ...] = get_args(get_args(Consequence)[0])

RollCheck.model_rebuild()
RollSave.model_rebuild()


def branches(consequence: "Consequence") -> Mapping[str, Sequence["Consequence"]]:
    if isinstance(consequence, DcRoll):
        return {"on_success": consequence.on_success, "on_failure": consequence.on_failure}
    return {}


def flatten(consequences: Sequence["Consequence"]) -> Iterator["Consequence"]:
    for consequence in consequences:
        yield consequence
        for branch in branches(consequence).values():
            yield from flatten(branch)


def _own_refs(consequence: "Consequence") -> Iterator[CanonRef]:
    for name, field in type(consequence).model_fields.items():
        marker = next((m for m in field.metadata if isinstance(m, References)), None)
        if marker is None:
            continue
        value: object = getattr(consequence, name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise TypeError(
                f"{type(consequence).__name__}.{name} is marked References "
                f"but holds a {type(value).__name__}"
            )
        yield EntityId(value), marker


def all_canon_refs(consequences: Sequence["Consequence"]) -> list[CanonRef]:
    return [ref for consequence in flatten(consequences) for ref in _own_refs(consequence)]
