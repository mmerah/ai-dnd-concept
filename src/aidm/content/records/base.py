from typing import Annotated, Literal

from pydantic import Field

from ...utils.dice import DiceExpr
from ...utils.models import Frozen
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

Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=64)]

CreatureSize = Literal["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]


class ContentRef(Frozen):
    """Uses a triple because indexes collide across collections and packs."""

    pack: Slug
    collection: Collection
    index: Slug

    def __str__(self) -> str:
        return f"{self.pack}/{self.collection}/{self.index}"

    def sibling(self, collection: Collection, index: Slug) -> "ContentRef":
        return ContentRef(pack=self.pack, collection=collection, index=index)


class Record(Frozen):
    index: Slug
    name: str


class DamageRoll(Frozen):
    dice: DiceExpr
    damage_type: DamageType


CoinUnit = Literal["cp", "sp", "gp"]


class Coin(Frozen):
    quantity: int = Field(ge=0)
    unit: CoinUnit

    def __str__(self) -> str:
        return f"{self.quantity} {self.unit}"
