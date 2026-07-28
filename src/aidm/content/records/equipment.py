"""Everything an `item` entity can point at: weapons, armour, gear, tools, vehicles, magic items.

Upstream ships all six as one 29-field type of which 24 are optional — optionality that states the
union of kinds, not anything about weapons. They are projected as separate non-optional models
discriminated on `equipment_category`, so a weapon that lost its damage is a load-time error rather
than a silent +0."""

from typing import ClassVar, Literal

from pydantic import Field

from ...utils.models import Frozen
from ..vocabulary import EquipmentCategory, WeaponProperty
from .base import Coin, Collection, DamageRoll, Record, Slug

WeaponCategory = Literal["Simple Melee", "Simple Ranged", "Martial Melee", "Martial Ranged"]
WeaponReach = Literal["Melee", "Ranged"]
ArmorCategory = Literal["Light", "Medium", "Heavy", "Shield"]
ToolCategory = Literal["Artisan's Tools", "Musical Instrument", "Gaming Sets", "Other Tools"]
VehicleCategory = Literal[
    "Mounts and Other Animals", "Tack, Harness, and Drawn Vehicles", "Waterborne Vehicles"
]
Rarity = Literal["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact", "Varies"]


class EquipmentRecord(Record):
    cost: Coin
    weight: float | None = None  # 22 records carry none; a scroll weighs nothing worth tracking
    desc: str = ""


class WeaponRange(Frozen):
    """Feet. Beyond `normal` an attack has disadvantage; beyond `long` it cannot be made."""

    normal: int = Field(ge=0)
    long: int | None = None


class WeaponRecord(EquipmentRecord):
    COLLECTION: ClassVar[Collection] = "weapons"
    category: WeaponCategory
    weapon_range: WeaponReach
    damage: DamageRoll | None = None
    # `versatile`'s consequence. The property is what says the two-handed grip is a choice.
    two_handed_damage: DamageRoll | None = None
    properties: tuple[WeaponProperty, ...] = ()
    range: WeaponRange
    throw_range: WeaponRange | None = None


class ArmorRecord(EquipmentRecord):
    COLLECTION: ClassVar[Collection] = "armor"
    category: ArmorCategory
    base_ac: int = Field(ge=0)
    dex_bonus: bool
    max_dex_bonus: int | None = None
    str_minimum: int = Field(ge=0)
    stealth_disadvantage: bool


class PackContents(Frozen):
    """What an equipment pack holds, by the index of another record in this collection."""

    index: Slug
    quantity: int = Field(ge=1)


class GearRecord(EquipmentRecord):
    COLLECTION: ClassVar[Collection] = "gear"
    gear_category: EquipmentCategory
    quantity: int | None = None
    contents: tuple[PackContents, ...] = ()


class ToolRecord(EquipmentRecord):
    COLLECTION: ClassVar[Collection] = "tools"
    tool_category: ToolCategory


class VehicleRecord(EquipmentRecord):
    COLLECTION: ClassVar[Collection] = "vehicles"
    vehicle_category: VehicleCategory
    speed: str | None = None  # '50 ft/round', '3 mph' — two units, so not an int
    capacity: str | None = None


class MagicItemRecord(Record):
    """The one collection whose mechanics stay prose: a magic item's effect is written as English
    with no structured payload upstream, and the Director can only turn it into words."""

    COLLECTION: ClassVar[Collection] = "magic_items"
    category: EquipmentCategory
    rarity: Rarity
    desc: str
    variant: bool = False
    variants: tuple[Slug, ...] = ()
