"""Monsters: the whole action economy, not just a to-hit and a damage die."""

from typing import Annotated, ClassVar, Literal

from pydantic import Field

from ...utils.dice import DiceExpr
from ...utils.models import EMPTY_FROZEN_MAP, Ability, Attributes, Frozen, FrozenMap
from ..vocabulary import ConditionName
from .base import Collection, ContentRef, CreatureSize, DamageRoll, Record, Slug

# One named action inside a multiattack routine, and how a save that lands is softened.
AttackType = Literal["melee", "ranged", "ability", "magic"]
SaveOutcome = Literal["none", "half"]
RestType = Literal["short", "long"]

MonsterType = Literal[
    "aberration",
    "beast",
    "celestial",
    "construct",
    "dragon",
    "elemental",
    "fey",
    "fiend",
    "giant",
    "humanoid",
    "monstrosity",
    "ooze",
    "plant",
    "swarm of Tiny beasts",
    "undead",
]


# Each arm renders itself, so a role's view of an action never has to match on the shape.
class RechargeOnRoll(Frozen):
    """ "Recharge 5-6": the action returns when this roll meets `min_value`."""

    kind: Literal["recharge_on_roll"] = "recharge_on_roll"
    dice: DiceExpr
    min_value: int = Field(ge=1)

    def __str__(self) -> str:
        return f"recharge {self.min_value}+ on {self.dice}"


class PerDay(Frozen):
    kind: Literal["per_day"] = "per_day"
    times: int = Field(ge=1)

    def __str__(self) -> str:
        return f"{self.times}/day"


class AtWill(Frozen):
    """Unlimited, and stated rather than absent: a spell cast at will is a different threat from one
    whose limit upstream simply did not record."""

    kind: Literal["at_will"] = "at_will"

    def __str__(self) -> str:
        return "at will"


class RechargeAfterRest(Frozen):
    kind: Literal["recharge_after_rest"] = "recharge_after_rest"
    rest_types: tuple[RestType, ...]

    def __str__(self) -> str:
        return f"recharges on a {' or '.join(self.rest_types)} rest"


# Without this a dragon's breath is unlimited, which is a different monster.
Usage = Annotated[RechargeOnRoll | PerDay | RechargeAfterRest | AtWill, Field(discriminator="kind")]


class MonsterActionBase(Frozen):
    """`damage` sits here rather than on the attack arm because 10 traits deal damage with neither a
    to-hit nor a save (a fire elemental's Fire Form), and dropping it would be a silent loss."""

    name: str
    desc: str
    usage: Usage | None = None
    damage: tuple[DamageRoll, ...] = ()


# Discriminated rather than a bag of optionals, so `engine/` cannot mistake a missing to-hit bonus
# for +0.
class MonsterAttack(MonsterActionBase):
    kind: Literal["attack"] = "attack"
    attack_bonus: int


class MonsterSave(MonsterActionBase):
    kind: Literal["save"] = "save"
    save_ability: Ability
    dc: int
    on_success: SaveOutcome


class MultiattackStep(Frozen):
    """One named action, repeated `count` times — exactly what `attack()` will iterate."""

    action_name: str
    count: int = Field(ge=1)
    attack_type: AttackType

    def __str__(self) -> str:
        return f"{self.action_name} x{self.count}"


class MultiattackOption(Frozen):
    steps: tuple[MultiattackStep, ...] = Field(min_length=1)

    def __str__(self) -> str:
        return " + ".join(str(step) for step in self.steps)


class MonsterMultiattack(MonsterActionBase):
    """A routine of other actions. One option is a fixed routine; several is a choice between them,
    which is the only difference between upstream's `actions` and `action_options` shapes."""

    kind: Literal["multiattack"] = "multiattack"
    options: tuple[MultiattackOption, ...] = Field(min_length=1)


class MonsterProcedure(MonsterActionBase):
    """An action this build still does not project mechanics for — a shapeshift, a summons. Prose
    here means *not yet typed*, not *untypeable*."""

    kind: Literal["procedure"] = "procedure"


MonsterAction = Annotated[
    MonsterAttack | MonsterSave | MonsterMultiattack | MonsterProcedure,
    Field(discriminator="kind"),
]


class MonsterSpell(Frozen):
    """Upstream carries `{name, level, url}` and no `index`, so the ref is derived from the url —
    the one place a reference has to be reconstructed rather than read."""

    ref: ContentRef
    name: str
    level: int = Field(ge=0, le=9)
    usage: Usage | None = None
    notes: str | None = None


class MonsterSpellcasting(Frozen):
    ability: Ability
    dc: int | None = None
    modifier: int | None = None
    level: int | None = None
    slots: FrozenMap[int, int] = EMPTY_FROZEN_MAP
    spells: tuple[MonsterSpell, ...] = ()


class Senses(Frozen):
    """Distances in feet. `passive_perception` is a DC the Director rolls stealth against."""

    passive_perception: int
    darkvision: int | None = None
    blindsight: int | None = None
    truesight: int | None = None
    tremorsense: int | None = None


class Speed(Frozen):
    """Distances in feet; a mode the monster lacks is absent, which is not the same as 0 (a ghost
    walks at 0 and flies at 40)."""

    walk: int | None = None
    fly: int | None = None
    swim: int | None = None
    climb: int | None = None
    burrow: int | None = None
    hover: bool = False


class MonsterRecord(Record):
    COLLECTION: ClassVar[Collection] = "monsters"
    size: CreatureSize
    type: MonsterType
    challenge_rating: float = Field(ge=0)
    armor_class: int = Field(ge=0)
    hit_points: int = Field(ge=1)
    hit_points_roll: DiceExpr
    attributes: Attributes
    speed: Speed
    senses: Senses
    # Free prose upstream ('bludgeoning, piercing, and slashing from nonmagical weapons'), and no
    # consequence carries a damage type yet: opaque until one does.
    damage_resistances: tuple[str, ...] = ()
    damage_immunities: tuple[str, ...] = ()
    damage_vulnerabilities: tuple[str, ...] = ()
    condition_immunities: tuple[ConditionName, ...] = ()
    saving_throws: FrozenMap[Ability, int] = EMPTY_FROZEN_MAP
    # Keyed by the index of a record in this pack's `skills`; the bonus is absolute, not a modifier.
    skills: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    actions: tuple[MonsterAction, ...] = ()
    legendary_actions: tuple[MonsterAction, ...] = ()
    reactions: tuple[MonsterAction, ...] = ()
    traits: tuple[MonsterAction, ...] = ()
    spellcasting: MonsterSpellcasting | None = None
