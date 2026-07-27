"""The 5e-database schema, as far as this pack projects it.

Tolerant of the 493 fields it does not read, and strict about the ones it does: a closed vocabulary
is narrowed *here*, at the boundary that read it, so a 14th damage type fails with the offending
value named rather than being narrowed later by a hand-written `match` per vocabulary."""

from pydantic import BaseModel, ConfigDict, Field

from aidm.content.records import (
    ArmorCategory,
    AttackType,
    CoinUnit,
    MonsterSize,
    MonsterType,
    Rarity,
    RestType,
    SaveOutcome,
    SpellAttackType,
    SpellSaveOutcome,
    ToolCategory,
    VehicleCategory,
    WeaponCategory,
    WeaponReach,
)
from aidm.content.vocabulary import (
    AlignmentName,
    ConditionName,
    DamageType,
    EquipmentCategory,
    LanguageName,
    MagicSchool,
    WeaponProperty,
)


class Upstream(BaseModel):
    """Tolerant of the fields we do not project, strict about the ones we do."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class ApiRef(Upstream):
    index: str


# Upstream is where a closed vocabulary is checked: a 14th damage type or a 16th condition must
# fail at the boundary that read it, with the offending value named, rather than be narrowed later
# by a hand-written `match` per vocabulary.
class DamageTypeRef(Upstream):
    index: DamageType


class SchoolRef(Upstream):
    index: MagicSchool


class ConditionRef(Upstream):
    index: ConditionName


class CategoryRef(Upstream):
    index: EquipmentCategory


class PropertyRef(Upstream):
    index: WeaponProperty


class Cost(Upstream):
    quantity: int
    unit: CoinUnit


class VehicleSpeed(Upstream):
    quantity: float  # a rowboat makes 1.5 mph
    unit: str


class Damage(Upstream):
    """Either dice of one type, or a `choose` between options."""

    damage_dice: str | None = None
    damage_type: DamageTypeRef | None = None
    options: "DamageOptions | None" = Field(default=None, alias="from")


class DamageOptions(Upstream):
    options: list[Damage]


Damage.model_rebuild()


class ActionDc(Upstream):
    dc_type: ApiRef
    dc_value: int
    success_type: SaveOutcome


class UpstreamUsage(Upstream):
    type: str
    dice: str | None = None
    min_value: int | None = None
    times: int | None = None
    rest_types: list[RestType] = Field(default_factory=list)


class MultiattackEntry(Upstream):
    action_name: str
    count: int | str
    type: AttackType


class ActionOption(Upstream):
    """One arm of a multiattack choice: either a single action, or several taken together."""

    option_type: str
    action_name: str | None = None
    count: int | None = None
    type: AttackType | None = None
    items: list["ActionOption"] = Field(default_factory=list)


ActionOption.model_rebuild()


class BreathOption(Upstream):
    name: str
    dc: ActionDc
    damage: list[Damage] = Field(default_factory=list)


class OptionSet[T](Upstream):
    options: list[T]


class Choice[T](Upstream):
    choose: int
    options: OptionSet[T] = Field(alias="from")


class Action(Upstream):
    name: str
    desc: str
    attack_bonus: int | None = None
    dc: ActionDc | None = None
    damage: list[Damage] = Field(default_factory=list)
    usage: UpstreamUsage | None = None
    actions: list[MultiattackEntry] = Field(default_factory=list)
    action_options: Choice[ActionOption] | None = None
    options: Choice[BreathOption] | None = None


class SpellSlot(Upstream):
    name: str
    level: int
    url: str
    usage: UpstreamUsage | None = None
    notes: str | None = None


class Spellcasting(Upstream):
    ability: ApiRef
    dc: int | None = None
    modifier: int | None = None
    level: int | None = None
    slots: dict[int, int] = Field(default_factory=dict)
    spells: list[SpellSlot] = Field(default_factory=list)


class SpecialAbility(Action):
    spellcasting: Spellcasting | None = None


class ArmorClass(Upstream):
    value: int


class Proficiency(Upstream):
    value: int
    proficiency: ApiRef


class Monster(Upstream):
    index: str
    name: str
    size: MonsterSize
    type: MonsterType
    challenge_rating: float
    armor_class: list[ArmorClass]
    hit_points: int
    hit_points_roll: str
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    speed: dict[str, str | bool]
    senses: dict[str, int | str]
    proficiencies: list[Proficiency] = Field(default_factory=list)
    damage_resistances: list[str] = Field(default_factory=list)
    damage_immunities: list[str] = Field(default_factory=list)
    damage_vulnerabilities: list[str] = Field(default_factory=list)
    condition_immunities: list[ConditionRef] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    legendary_actions: list[Action] = Field(default_factory=list)
    reactions: list[Action] = Field(default_factory=list)
    special_abilities: list[SpecialAbility] = Field(default_factory=list)


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


class SpellDc(Upstream):
    dc_type: ApiRef
    dc_success: SpellSaveOutcome


class SpellScaling(Upstream):
    damage_type: DamageTypeRef | None = None
    damage_at_slot_level: dict[int, str] = Field(default_factory=dict)
    damage_at_character_level: dict[int, str] = Field(default_factory=dict)


class Spell(Upstream):
    index: str
    name: str
    desc: list[str]
    level: int
    school: SchoolRef
    casting_time: str
    range: str
    duration: str
    concentration: bool
    ritual: bool
    attack_type: SpellAttackType | None = None
    dc: SpellDc | None = None
    damage: SpellScaling | None = None
    heal_at_slot_level: dict[int, str] = Field(default_factory=dict)


class Skill(Upstream):
    index: str
    name: str
    ability_score: ApiRef


class Condition(Upstream):
    index: ConditionName
    name: str
    desc: list[str]


class Alignment(Upstream):
    index: AlignmentName
    name: str
    abbreviation: str
    desc: str


class Language(Upstream):
    index: LanguageName
    name: str
    script: str | None = None
    typical_speakers: list[str] = Field(default_factory=list)


class PackageJson(Upstream):
    version: str
