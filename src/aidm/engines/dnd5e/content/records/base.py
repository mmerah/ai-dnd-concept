from typing import Literal

from pydantic import Field

from ...dice import DiceExpr
from ...values import ContentSlug, Value
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


class ContentRef(Value):
    """Uses a triple because indexes collide across collections and packs."""

    pack: ContentSlug
    collection: Collection
    index: ContentSlug

    def __str__(self) -> str:
        return f"{self.pack}/{self.collection}/{self.index}"

    def sibling(self, collection: Collection, index: ContentSlug) -> "ContentRef":
        return ContentRef(pack=self.pack, collection=collection, index=index)


class Record(Value):
    index: ContentSlug
    name: str


class DamageRoll(Value):
    dice: DiceExpr
    damage_type: DamageType


CoinUnit = Literal["cp", "sp", "gp"]


class Coin(Value):
    quantity: int = Field(ge=0)
    unit: CoinUnit

    def __str__(self) -> str:
        return f"{self.quantity} {self.unit}"
