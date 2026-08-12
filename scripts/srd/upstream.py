"""The 5e-database schema, as far as the pack projects it: tolerant of the hundreds of fields
that stay in prose, strict about the few that become numbers and notes."""

from pydantic import BaseModel, ConfigDict, Field


class Upstream(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Label(Upstream):
    name: str


class Named(Label):
    index: str


class Described(Named):
    desc: list[str] | str = ""


class Quantity(Upstream):
    quantity: float
    unit: str


class Option(Upstream):
    option_type: str = ""
    item: Named | None = None
    string: str = ""
    # Background ideals are the one option shape carrying prose and alignments of their own.
    desc: str = ""
    alignments: list[Label] = []
    # A multiclass prerequisite choice offers ability-score minima instead of items.
    ability_score: Label | None = None
    minimum_score: int | None = None
    # Starting equipment: one item, several at once, or a category left open. Upstream's `count`
    # stays unread — one ref is one carried item, which is all a sheet holds.
    of: Named | None = None
    items: list["Option"] = []
    choice: "Choice | None" = None


class OptionSet(Upstream):
    # Enemy- and terrain-type choices list bare strings where every other choice lists objects.
    options: list[Option | str] = []
    # A background's or class's equipment pick names a whole category instead of listing options.
    equipment_category: Named | None = None


class Choice(Upstream):
    desc: str = ""
    choose: int
    # A factory, not an instance: `Option` names `Choice`, so no `OptionSet` exists to build yet.
    options: OptionSet = Field(default_factory=OptionSet, alias="from")


class ArmorClass(Upstream):
    type: str
    value: int
    spell: Label | None = None
    condition: Label | None = None
    armor: list[Named] = []
    desc: str = ""


class MonsterProficiency(Upstream):
    value: int
    proficiency: Named


class Damage(Upstream):
    damage_dice: str = ""
    damage_type: Label | None = None


class SaveDc(Upstream):
    dc_type: Label
    dc_value: int
    success_type: str = ""


class ActionDamageSet(Upstream):
    options: list["ActionDamage"] = []


class ActionDamage(Damage):
    """A monster action's damage entry: possibly save-gated (the assassin's poison rider), or a
    choice between variants (a wight's one- or two-handed longsword)."""

    dc: SaveDc | None = None
    notes: str = ""
    choose: int | None = None
    options: ActionDamageSet = Field(default_factory=ActionDamageSet, alias="from")


class Usage(Upstream):
    type: str
    times: int | None = None
    dice: str = ""
    min_value: int | None = None
    rest_types: list[str] = []


class ActionRef(Upstream):
    action_name: str
    count: int | str
    type: str = ""


class ActionRefOption(Upstream):
    action_name: str = ""
    count: int | str = ""
    items: list[ActionRef] = []


class ActionRefSet(Upstream):
    options: list[ActionRefOption] = []


class ActionRefChoice(Upstream):
    choose: int
    options: ActionRefSet = Field(default=ActionRefSet(), alias="from")


class ActionOption(Upstream):
    name: str = ""
    dc: SaveDc | None = None
    damage: list[ActionDamage] = []


class ActionOptionSet(Upstream):
    options: list[ActionOption] = []


class ActionChoice(Upstream):
    options: ActionOptionSet = Field(default=ActionOptionSet(), alias="from")


class MonsterSpell(Upstream):
    name: str
    level: int


class MonsterSpellcasting(Upstream):
    dc: int | None = None
    modifier: int | None = None
    slots: dict[str, int] = {}
    spells: list[MonsterSpell] = []


class ActionAttack(Upstream):
    """The androsphinx's Roar: a flat sequence of named saves inside one action."""

    name: str
    dc: SaveDc | None = None
    damage: list[ActionDamage] = []


class Action(Upstream):
    name: str
    desc: str
    attack_bonus: int | None = None
    dc: SaveDc | None = None
    damage: list[ActionDamage] = []
    usage: Usage | None = None
    actions: list[ActionRef] = []
    action_options: ActionRefChoice | None = None
    attacks: list[ActionAttack] = []
    options: ActionChoice | None = None
    spellcasting: MonsterSpellcasting | None = None


class Monster(Named):
    desc: list[str] | str = ""
    forms: list[Named] = []
    size: str
    type: str
    subtype: str | None = None
    alignment: str
    armor_class: list[ArmorClass]
    hit_points: int
    hit_points_roll: str
    speed: dict[str, str | bool] = {}
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    proficiencies: list[MonsterProficiency] = []
    damage_vulnerabilities: list[str] = []
    damage_resistances: list[str] = []
    damage_immunities: list[str] = []
    condition_immunities: list[Named] = []
    senses: dict[str, str | int] = {}
    languages: str = ""
    challenge_rating: float
    proficiency_bonus: int
    xp: int
    special_abilities: list[Action] = []
    actions: list[Action] = []
    legendary_actions: list[Action] = []
    reactions: list[Action] = []


class SpellDc(Upstream):
    dc_type: Label
    dc_success: str = ""
    desc: str = ""


class SpellDamage(Upstream):
    damage_type: Label | None = None
    damage_at_slot_level: dict[str, str] = {}
    damage_at_character_level: dict[str, str] = {}


class AreaOfEffect(Upstream):
    type: str
    size: int


class Spell(Described):
    level: int
    school: Label
    casting_time: str
    range: str
    duration: str
    components: list[str] = []
    material: str = ""
    ritual: bool = False
    concentration: bool = False
    higher_level: list[str] = []
    attack_type: str = ""
    dc: SpellDc | None = None
    damage: SpellDamage | None = None
    heal_at_slot_level: dict[str, str] = {}
    area_of_effect: AreaOfEffect | None = None
    classes: list[Label] = []
    subclasses: list[Label] = []


class Range(Upstream):
    normal: int
    long: int | None = None


class ArmorValue(Upstream):
    base: int
    dex_bonus: bool
    max_bonus: int | None = None


class Contained(Upstream):
    item: Label
    quantity: int


class Equipment(Described):
    equipment_category: Named
    cost: Quantity | None = None
    weight: float | None = None
    gear_category: Label | None = None
    contents: list[Contained] = []
    # Weapons
    category_range: str = ""
    weapon_range: str = ""
    damage: Damage | None = None
    two_handed_damage: Damage | None = None
    range: Range | None = None
    throw_range: Range | None = None
    properties: list[Named] = []
    special: list[str] = []
    # Armor
    armor_category: str = ""
    armor_class: ArmorValue | None = None
    str_minimum: int | None = None
    stealth_disadvantage: bool | None = None
    # Vehicles and containers
    tool_category: str = ""
    vehicle_category: str = ""
    speed: Quantity | None = None
    capacity: str = ""
    # Ammunition bundles
    quantity: int | None = None


class MagicItem(Described):
    equipment_category: Label
    rarity: Label
    variant: bool = False
    variants: list[Named] = []


class Race(Described):
    speed: int
    ability_bonuses: list["AbilityBonus"] = []
    ability_bonus_options: Choice | None = None
    alignment: str = ""
    age: str = ""
    size: str = ""
    size_description: str = ""
    language_desc: str = ""
    languages: list[Named] = []
    language_options: Choice | None = None
    traits: list[Label] = []
    subraces: list[Label] = []


class AbilityBonus(Upstream):
    ability_score: Label
    bonus: int


class Subrace(Described):
    race: Named
    ability_bonuses: list[AbilityBonus] = []
    racial_traits: list[Named] = []


class Background(Named):
    starting_proficiencies: list[Named] = []
    language_options: Choice | None = None
    starting_equipment: list["Carried"] = []
    starting_equipment_options: list[Choice] = []
    starting_gold: Quantity | None = None
    feature: "BackgroundFeature | None" = None
    personality_traits: Choice | None = None
    ideals: Choice | None = None
    bonds: Choice | None = None
    flaws: Choice | None = None


class Carried(Upstream):
    equipment: Named
    quantity: int


class BackgroundFeature(Upstream):
    name: str
    desc: list[str] = []


class Class(Named):
    hit_die: int
    proficiencies: list[Label] = []
    proficiency_choices: list[Choice] = []
    saving_throws: list[Label] = []
    starting_equipment: list[Carried] = []
    starting_equipment_options: list[Choice] = []
    multi_classing: "MultiClassing | None" = None
    subclasses: list[Label] = []
    spellcasting: "Spellcasting | None" = None


class MultiClassing(Upstream):
    # Most classes require every listed minimum; the fighter alone offers a choice instead.
    prerequisites: list["Prerequisite"] = []
    prerequisite_options: Choice | None = None
    proficiencies: list[Label] = []
    proficiency_choices: list[Choice] = []


class Spellcasting(Upstream):
    spellcasting_ability: Label
    level: int | None = None
    info: list[BackgroundFeature] = []


class SubclassSpell(Upstream):
    prerequisites: list[Named] = []
    spell: Named


class Subclass(Described):
    class_: Named = Field(alias="class")
    subclass_flavor: str = ""
    spells: list[SubclassSpell] = []


class FeatureSpecific(Upstream):
    subfeature_options: Choice | None = None
    expertise_options: Choice | None = None
    enemy_type_options: Choice | None = None
    terrain_type_options: Choice | None = None
    # The warlock's invocation list is flat: how many to know is the level row's number.
    invocations: list[Named] = []


class FeaturePrerequisite(Upstream):
    type: str
    level: int | None = None
    feature: str = ""
    spell: str = ""


class Feature(Described):
    level: int
    class_: Label | None = Field(default=None, alias="class")
    subclass: Label | None = None
    parent: Label | None = None
    feature_specific: FeatureSpecific | None = None
    prerequisites: list[FeaturePrerequisite] = []


class DieLadder(Upstream):
    dice_count: int
    dice_value: int


class SlotCreation(Upstream):
    sorcery_point_cost: int
    spell_slot_level: int


class Level(Upstream):
    index: str
    level: int
    prof_bonus: int | None = None
    ability_score_bonuses: int | None = None
    features: list[Named] = []
    class_specific: dict[str, object] = {}
    subclass_specific: dict[str, object] = {}
    spellcasting: dict[str, int] = {}
    class_: Named = Field(alias="class")
    subclass: Named | None = None


class BreathDc(Upstream):
    dc_type: Label
    success_type: str = ""


class BreathWeapon(Upstream):
    dc: BreathDc | None = None
    damage: list[SpellDamage] = []
    area_of_effect: AreaOfEffect | None = None
    usage: Usage | None = None


class TraitSpecific(Upstream):
    damage_type: Label | None = None
    breath_weapon: BreathWeapon | None = None
    subtrait_options: Choice | None = None
    spell_options: Choice | None = None


class Trait(Described):
    races: list[Label] = []
    subraces: list[Label] = []
    proficiencies: list[Label] = []
    proficiency_choices: Choice | None = None
    language_options: Choice | None = None
    parent: Label | None = None
    trait_specific: TraitSpecific | None = None


class Feat(Described):
    prerequisites: list["Prerequisite"] = []


class Prerequisite(Upstream):
    ability_score: Label
    minimum_score: int


class Skill(Described):
    ability_score: Label


class Language(Described):
    type: str
    script: str = ""
    typical_speakers: list[str] = []


class Proficiency(Named):
    type: str
    reference: Named


class Alignment(Described):
    abbreviation: str
