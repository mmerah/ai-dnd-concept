from collections.abc import Mapping, Sequence
from typing import Annotated, ClassVar, Literal, get_args

from pydantic import Field, TypeAdapter

from aidm.actions import (
    Discover,
    DropItem,
    GainImprovisedItem,
    GiveItem,
    Move,
    TakeItem,
)
from aidm.base import PLAYER_ID, EntityId
from aidm.directing import ConsequenceBase, Reference
from aidm.transition import Direction

from .content.records.spells import MAX_SPELL_LEVEL, SpellLevel
from .content.vocabulary import CONDITION_NAMES, ConditionName, RestType
from .dice import SelfContainedDice
from .identity import ENGINE_ID
from .state import FeatureKey, SpellKey
from .values import ABILITIES, Ability, Value

# The consuming action owns the sign, so magnitudes stay non-negative.
Magnitude = SelfContainedDice | Annotated[int, Field(ge=0, strict=True)]


class Action(ConsequenceBase):
    pass


class LevelUp(Action):
    """Unlock the player's next level-up."""

    GUIDANCE: ClassVar[str] = """Use once when the player's achievements earn a new level. This \
unlocks the level-up UI where the player makes any character choices; it does not choose or apply \
the level itself. Do not use it while the player's state says an advancement is already waiting."""

    action: Literal["level_up"] = "level_up"


class UseFeature(Action):
    """Use one of the player's active class features."""

    GUIDANCE: ClassVar[str] = """Use when the player invokes a feature marked `usable` in their \
feature list. Copy its exact feature id. The rules verify ownership and remaining uses, and apply \
effects marked `engine-resolved`. For a `description-guided` feature, propose any concrete \
consequences the description requires alongside this activation."""

    action: Literal["use_feature"] = "use_feature"
    feature: FeatureKey = Field(description="Exact id of an owned feature marked `usable`.")
    amount: int = Field(
        default=1,
        ge=1,
        description="Resource points spent; use 1 unless the feature allows a chosen amount.",
    )


class Cast(Action):
    """The player casts one of the spells they can cast; the rules spend the slot and resolve it."""

    GUIDANCE: ClassVar[str] = """Use when the player casts a spell listed in their spell list. \
Copy its exact spell id, and give the level of the slot they spend — the spell's own level or \
higher, or 0 for a cantrip. The rules verify the spell, the slot and any attack roll, save, damage \
or healing; whether it lands is never yours to decide, so do not wrap it in a `roll_check`. \
Whatever the spell's description does beyond that is yours to propose as ordinary consequences \
alongside it.
Example: they hurl a fireball at the ghoul -> `cast` with spell \
`srd-2014/spells/fireball`, slot_level 3, target_id `ghoul`."""

    action: Literal["cast"] = "cast"
    spell: SpellKey = Field(description="Exact id of a spell from the player's spell list.")
    slot_level: SpellLevel = Field(
        description=f"Level of the slot spent, 1-{MAX_SPELL_LEVEL}; 0 for a cantrip."
    )
    target_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
        default=None, description="Id of the `actor` aimed at, here with the player; omit for them."
    )


class Rest(Action):
    """Complete a short or long rest."""

    GUIDANCE: ClassVar[str] = """Use only when the fiction establishes that the player completes \
the rest. This recharges the features and spell slots that the rest is long enough to restore; it \
does not invent healing or other rest benefits."""

    action: Literal["rest"] = "rest"
    rest: RestType = Field(description="The completed rest: `short` or `long`.")


class Damage(Action):
    """Reduce an actor's hit points by dice you roll, or by a flat amount."""

    GUIDANCE: ClassVar[str] = """Use when someone here takes damage. Prefer dice — '1d6', \
'2d6 + 3' — and let them fall; a flat number is for harm with nothing left to chance. Whether a \
blow lands is never yours to decide: put the damage in a `roll_check` branch.
Example: a trap catches the player -> `damage` with amount '2d4'. Kael swings at Mara -> \
`roll_check` whose on_success is `damage` with amount '1d8', target_id `mara`."""

    action: Literal["damage"] = "damage"
    amount: Magnitude = Field(description="Hit points lost: dice like '2d6', or a number >= 0.")
    target_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
        default=None, description="Id of the `actor` harmed, here with the player; omit for them."
    )


class Heal(Action):
    """Restore an actor's hit points by dice you roll, or by a flat amount."""

    GUIDANCE: ClassVar[str] = """Use when someone here is healed; the same amount and target rules \
as `damage`. Example: a poultice on the player -> `heal` with amount '1d4 + 2'."""

    action: Literal["heal"] = "heal"
    amount: Magnitude = Field(description="Hit points restored: dice like '1d4', or a number >= 0.")
    target_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
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
    target_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
        default=None, description="Id of the `actor` affected, here with the player; omit for them."
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
    target_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
        default=None,
        description="Id of the `actor` struck at, here with the player; omit for them.",
    )
    attacker_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
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
    target_id: Annotated[EntityId | None, Reference("actor", present=True)] = Field(
        default=None,
        description="Id of the `actor` resisting, here with the player; omit for them.",
    )


Consequence = Annotated[
    Discover
    | TakeItem
    | DropItem
    | GiveItem
    | GainImprovisedItem
    | LevelUp
    | UseFeature
    | Cast
    | Rest
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


MECHANICS_ADAPTER: TypeAdapter[list[Consequence]] = TypeAdapter(list[Consequence])


class Dnd5eDirection(Value):
    """A proposed attempt, not a resolved outcome."""

    intent: str
    tone: str
    speaker_id: EntityId | None = None
    mechanics: list[Consequence] = Field(default_factory=list)


def dump_direction(proposal: Dnd5eDirection) -> Direction:
    """The Director proposes typed mechanics; core only ever holds the flat blob."""
    return Direction(
        engine=ENGINE_ID,
        intent=proposal.intent,
        tone=proposal.tone,
        speaker_id=proposal.speaker_id,
        mechanics=MECHANICS_ADAPTER.dump_python(proposal.mechanics, mode="json"),
    )


def load_mechanics(direction: Direction) -> list[Consequence]:
    """The tag is checked too: core actions validate under either engine, so shape cannot decide."""
    if direction.engine != ENGINE_ID:
        raise ValueError(f"5e received a {direction.engine!r} direction")
    return MECHANICS_ADAPTER.validate_python(direction.mechanics)
