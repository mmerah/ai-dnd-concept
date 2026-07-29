"""Weapons, armour, gear, tools, vehicles and magic items: one upstream type covering all of them.

Optionality here is a statement about the union of kinds, not about weapons — which is why they are
projected as separate non-optional models."""

from pydantic import Field

from aidm.content.records.base import CoinUnit
from aidm.content.records.equipment import (
    ArmorCategory,
    Rarity,
    ToolCategory,
    VehicleCategory,
    WeaponCategory,
    WeaponReach,
)
from aidm.content.vocabulary import EquipmentCategory

from .base import ApiRef, CategoryRef, Damage, PropertyRef, Upstream


class Cost(Upstream):
    quantity: int
    unit: CoinUnit


class VehicleSpeed(Upstream):
    quantity: float  # a rowboat makes 1.5 mph
    unit: str


class ArmorStats(Upstream):
    base: int
    dex_bonus: bool
    max_bonus: int | None = None


class Contents(Upstream):
    item: ApiRef
    quantity: int


class Equipment(Upstream):
    """Weapons, armour, gear, tools and vehicles are projected as separate non-optional models:
    upstream optionality here is a statement about the union of kinds, not about weapons."""

    index: str
    name: str
    equipment_category: ApiRef
    cost: Cost
    weight: float | None = None
    desc: list[str] = Field(default_factory=list)
    category_range: WeaponCategory | None = None
    weapon_range: WeaponReach | None = None
    damage: Damage | None = None
    two_handed_damage: Damage | None = None
    properties: list[PropertyRef] = Field(default_factory=list)
    range: dict[str, int] = Field(default_factory=dict)
    throw_range: dict[str, int] | None = None
    armor_category: ArmorCategory | None = None
    armor_class: ArmorStats | None = None
    str_minimum: int | None = None
    stealth_disadvantage: bool | None = None
    gear_category: CategoryRef | None = None
    quantity: int | None = None
    contents: list[Contents] = Field(default_factory=list)
    tool_category: ToolCategory | None = None
    vehicle_category: VehicleCategory | None = None
    speed: VehicleSpeed | None = None
    capacity: str | None = None


class ItemRarity(Upstream):
    name: Rarity


class MagicItem(Upstream):
    index: str
    name: str
    equipment_category: CategoryRef
    rarity: ItemRarity
    desc: list[str] = Field(default_factory=list)
    variant: bool = False
    variants: list[ApiRef] = Field(default_factory=list)


class EquipmentCategoryRecord(Upstream):
    index: EquipmentCategory
    equipment: list[ApiRef] = Field(default_factory=list)
