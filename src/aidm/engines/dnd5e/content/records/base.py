from typing import Literal

from pydantic import Field

from aidm.core.packs import Value

from ...dice import DiceExpr
from ..vocabulary import DamageType

Collection = Literal[
    "monsters",
    "weapons",
    "armor",
    "gear",
    "tools",
    "vehicles",
    "magic_items",
    "spells",
    "skills",
    "conditions",
    "alignments",
    "languages",
    "classes",
    "subclasses",
    "levels",
    "features",
    "races",
    "subraces",
    "traits",
    "backgrounds",
    "feats",
    "proficiencies",
]

CreatureSize = Literal["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]


class DamageRoll(Value):
    dice: DiceExpr
    damage_type: DamageType


CoinUnit = Literal["cp", "sp", "gp"]


class Coin(Value):
    quantity: int = Field(ge=0)
    unit: CoinUnit

    def __str__(self) -> str:
        return f"{self.quantity} {self.unit}"
