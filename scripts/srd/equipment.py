"""Weapons, armour, gear, tools, vehicles and magic items: one upstream type, six models."""

from aidm.plugins.dnd5e.content.records.base import Coin
from aidm.plugins.dnd5e.content.records.equipment import (
    ArmorRecord,
    GearRecord,
    MagicItemRecord,
    PackContents,
    ToolRecord,
    VehicleRecord,
    WeaponRange,
    WeaponRecord,
)

from .common import damage_roll, owner_of
from .upstream.equipment import Equipment, MagicItem


def _cost(item: Equipment) -> Coin:
    return Coin(quantity=item.cost.quantity, unit=item.cost.unit)


def _desc(item: Equipment) -> str:
    return "\n\n".join(item.desc)


def _weapon_range(distances: dict[str, int] | None) -> WeaponRange | None:
    if distances is None:
        return None
    return WeaponRange(normal=distances["normal"], long=distances.get("long"))


def weapon(item: Equipment) -> WeaponRecord:
    if item.category_range is None or item.weapon_range is None:
        raise ValueError(f"weapon {item.index!r} has no category or range band")
    owner = owner_of("weapons", item.index)
    normal = _weapon_range(item.range)
    if normal is None:
        raise ValueError(f"weapon {item.index!r} has no range")
    return WeaponRecord(
        index=item.index,
        name=item.name,
        cost=_cost(item),
        weight=item.weight,
        desc=_desc(item),
        category=item.category_range,
        weapon_range=item.weapon_range,
        damage=None if item.damage is None else damage_roll(item.damage, owner),
        two_handed_damage=(
            None if item.two_handed_damage is None else damage_roll(item.two_handed_damage, owner)
        ),
        properties=tuple(p.index for p in item.properties),
        range=normal,
        throw_range=_weapon_range(item.throw_range),
    )


def armor(item: Equipment) -> ArmorRecord:
    """Optional upstream only because one type covers 237 records: all 13 armour records carry every
    field below, so an absent one means upstream moved — and a default would arm plate at Str 0."""
    if (
        item.armor_category is None
        or item.armor_class is None
        or item.str_minimum is None
        or item.stealth_disadvantage is None
    ):
        raise ValueError(f"armor {item.index!r} is missing a projected field")
    return ArmorRecord(
        index=item.index,
        name=item.name,
        cost=_cost(item),
        weight=item.weight,
        desc=_desc(item),
        category=item.armor_category,
        base_ac=item.armor_class.base,
        dex_bonus=item.armor_class.dex_bonus,
        max_dex_bonus=item.armor_class.max_bonus,
        str_minimum=item.str_minimum,
        stealth_disadvantage=item.stealth_disadvantage,
    )


def gear(item: Equipment) -> GearRecord:
    if item.gear_category is None:
        raise ValueError(f"gear {item.index!r} sits on no shelf")
    return GearRecord(
        index=item.index,
        name=item.name,
        cost=_cost(item),
        weight=item.weight,
        desc=_desc(item),
        gear_category=item.gear_category.index,
        quantity=item.quantity,
        contents=tuple(
            PackContents(index=c.item.index, quantity=c.quantity) for c in item.contents
        ),
    )


def tool(item: Equipment) -> ToolRecord:
    if item.tool_category is None:
        raise ValueError(f"tool {item.index!r} has no category")
    return ToolRecord(
        index=item.index,
        name=item.name,
        cost=_cost(item),
        weight=item.weight,
        desc=_desc(item),
        tool_category=item.tool_category,
    )


def vehicle(item: Equipment) -> VehicleRecord:
    if item.vehicle_category is None:
        raise ValueError(f"vehicle {item.index!r} has no category")
    return VehicleRecord(
        index=item.index,
        name=item.name,
        cost=_cost(item),
        weight=item.weight,
        desc=_desc(item),
        vehicle_category=item.vehicle_category,
        speed=None if item.speed is None else f"{item.speed.quantity} {item.speed.unit}",
        capacity=item.capacity,
    )


def magic_item(item: MagicItem) -> MagicItemRecord:
    return MagicItemRecord(
        index=item.index,
        name=item.name,
        category=item.equipment_category.index,
        rarity=item.rarity.name,
        desc="\n\n".join(item.desc),
        variant=item.variant,
        variants=tuple(v.index for v in item.variants),
    )
