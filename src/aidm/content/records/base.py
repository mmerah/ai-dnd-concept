"""What every record shares, and the reference that addresses one."""

from typing import Annotated, Literal

from pydantic import Field

from ...utils.dice import DiceExpr
from ...utils.models import Frozen
from ..vocabulary import DamageType

# The 12 collections this build projects. It is deliberately wider than the records that exist:
# `Manifest.provides` can only declare a gap in a collection it can name.
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
]

Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", max_length=64)]


class ContentRef(Frozen):
    """Where a record lives. The 2014 pack alone holds 79 cross-collection `index` collisions —
    `shield` is a Spell and an Equipment, `goblin` a Language and a Monster — so a record's identity
    is this triple, never a slug. Naming the pack also makes implicit last-wins shadowing between
    packs unrepresentable: two packs cannot claim one ref."""

    pack: Slug
    collection: Collection
    index: Slug

    def __str__(self) -> str:
        return f"{self.pack}/{self.collection}/{self.index}"


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
