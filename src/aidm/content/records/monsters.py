from typing import Annotated, Literal

from pydantic import Field

from ...utils.dice import DiceExpr
from ...utils.models import EMPTY_FROZEN_MAP, Ability, Attributes, Frozen, FrozenMap
from ..vocabulary import ConditionName
from .base import ContentRef, CreatureSize, DamageRoll, Record, Slug

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


class RechargeOnRoll(Frozen):
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
    kind: Literal["at_will"] = "at_will"

    def __str__(self) -> str:
        return "at will"


class RechargeAfterRest(Frozen):
    kind: Literal["recharge_after_rest"] = "recharge_after_rest"
    rest_types: tuple[RestType, ...]

    def __str__(self) -> str:
        return f"recharges on a {' or '.join(self.rest_types)} rest"


Usage = Annotated[RechargeOnRoll | PerDay | RechargeAfterRest | AtWill, Field(discriminator="kind")]


class MonsterActionBase(Frozen):
    """Damage is shared because some traits have neither an attack nor a save."""

    name: str
    desc: str
    usage: Usage | None = None
    damage: tuple[DamageRoll, ...] = ()


class MonsterAttack(MonsterActionBase):
    kind: Literal["attack"] = "attack"
    attack_bonus: int


class MonsterSave(MonsterActionBase):
    kind: Literal["save"] = "save"
    save_ability: Ability
    dc: int
    on_success: SaveOutcome


class MultiattackStep(Frozen):
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
    kind: Literal["multiattack"] = "multiattack"
    options: tuple[MultiattackOption, ...] = Field(min_length=1)


class MonsterProcedure(MonsterActionBase):
    """Keeps untyped procedures so importing a pack remains lossless."""

    kind: Literal["procedure"] = "procedure"


MonsterAction = Annotated[
    MonsterAttack | MonsterSave | MonsterMultiattack | MonsterProcedure,
    Field(discriminator="kind"),
]


class MonsterSpell(Frozen):
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
    passive_perception: int
    darkvision: int | None = None
    blindsight: int | None = None
    truesight: int | None = None
    tremorsense: int | None = None


class Speed(Frozen):
    """Uses `None` for absent modes because zero is meaningful."""

    walk: int | None = None
    fly: int | None = None
    swim: int | None = None
    climb: int | None = None
    burrow: int | None = None
    hover: bool = False


class MonsterRecord(Record):
    size: CreatureSize
    type: MonsterType
    challenge_rating: float = Field(ge=0)
    armor_class: int = Field(ge=0)
    hit_points: int = Field(ge=1)
    hit_points_roll: DiceExpr
    attributes: Attributes
    speed: Speed
    senses: Senses
    # Opaque until consequences carry damage types.
    damage_resistances: tuple[str, ...] = ()
    damage_immunities: tuple[str, ...] = ()
    damage_vulnerabilities: tuple[str, ...] = ()
    condition_immunities: tuple[ConditionName, ...] = ()
    saving_throws: FrozenMap[Ability, int] = EMPTY_FROZEN_MAP
    skills: FrozenMap[Slug, int] = EMPTY_FROZEN_MAP
    actions: tuple[MonsterAction, ...] = ()
    legendary_actions: tuple[MonsterAction, ...] = ()
    reactions: tuple[MonsterAction, ...] = ()
    traits: tuple[MonsterAction, ...] = ()
    spellcasting: MonsterSpellcasting | None = None
