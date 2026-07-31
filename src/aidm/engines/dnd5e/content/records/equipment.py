from typing import Literal

from pydantic import Field

from ...values import ContentSlug, Value
from ..vocabulary import EquipmentCategory, WeaponProperty
from .base import Coin, DamageRoll, Record

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
    weight: float | None = None
    desc: str = ""


class WeaponRange(Value):
    normal: int = Field(ge=0)
    long: int | None = None


class WeaponRecord(EquipmentRecord):
    category: WeaponCategory
    weapon_range: WeaponReach
    damage: DamageRoll | None = None
    two_handed_damage: DamageRoll | None = None
    properties: tuple[WeaponProperty, ...] = ()
    range: WeaponRange
    throw_range: WeaponRange | None = None


class ArmorRecord(EquipmentRecord):
    category: ArmorCategory
    base_ac: int = Field(ge=0)
    dex_bonus: bool
    max_dex_bonus: int | None = None
    str_minimum: int = Field(ge=0)
    stealth_disadvantage: bool


class PackContents(Value):
    index: ContentSlug
    quantity: int = Field(ge=1)


class GearRecord(EquipmentRecord):
    gear_category: EquipmentCategory
    quantity: int | None = None
    contents: tuple[PackContents, ...] = ()


class ToolRecord(EquipmentRecord):
    tool_category: ToolCategory


class VehicleRecord(EquipmentRecord):
    vehicle_category: VehicleCategory
    speed: str | None = None
    capacity: str | None = None


class MagicItemRecord(Record):
    category: EquipmentCategory
    rarity: Rarity
    desc: str
    variant: bool = False
    variants: tuple[ContentSlug, ...] = ()
