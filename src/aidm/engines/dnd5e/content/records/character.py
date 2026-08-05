from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aidm.core.dice import PositiveDice
from aidm.core.packs import EMPTY_FROZEN_MAP, ContentRef, ContentSlug, FrozenMap, Record, Value

from ...values import Ability
from ..vocabulary import LanguageName, RestType
from .base import CreatureSize


class AbilityBonus(Value):
    ability: Ability
    bonus: int = Field(ge=1)

    def __str__(self) -> str:
        return f"+{self.bonus} {self.ability}"


class RecordOption(Value):
    kind: Literal["record"] = "record"
    label: str
    ref: ContentRef

    @property
    def key(self) -> str:
        return self.ref.index


class BonusOption(Value):
    kind: Literal["bonus"] = "bonus"
    bonus: AbilityBonus

    @property
    def key(self) -> str:
        return self.bonus.ability

    @property
    def label(self) -> str:
        return str(self.bonus)


ChoiceOption = Annotated[RecordOption | BonusOption, Field(discriminator="kind")]

# Expertise offers the same options as a grant, so the choice carries the effect.
ChoiceEffect = Literal["grant", "double"]


class ProgressionChoice(Value):
    """IDs stay stable because persisted decisions are keyed by them."""

    id: ContentSlug
    prompt: str
    choose: int = Field(ge=1)
    # Repetition represents spending both +1 picks on one ability.
    distinct: bool = True
    effect: ChoiceEffect = "grant"
    options: tuple[ChoiceOption, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _satisfiable(self) -> Self:
        keys = [o.key for o in self.options]
        if len(set(keys)) != len(keys):
            raise ValueError(f"choice {self.id!r} offers one key twice: {sorted(keys)}")
        if self.distinct and self.choose > len(keys):
            raise ValueError(f"choice {self.id!r} asks for {self.choose} of {len(keys)} options")
        if self.effect == "double" and any(
            not isinstance(option, RecordOption) or option.ref.collection != "proficiencies"
            for option in self.options
        ):
            raise ValueError(f"choice {self.id!r} can only double proficiencies")
        return self

    def option(self, key: str) -> ChoiceOption | None:
        return next((o for o in self.options if o.key == key), None)


class SubclassChoice(Value):
    """Lives on the class because its feature provides only prose."""

    level: int = Field(ge=1, le=20)
    options: tuple[ContentSlug, ...] = Field(min_length=1)


class ClassSpellcasting(Value):
    ability: Ability
    # Pact Magic returns on a short rest; every other list returns only on a long one.
    slot_recharge: RestType


class ClassRecord(Record):
    hit_die: int = Field(ge=1)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[ContentSlug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    subclass: SubclassChoice | None = None
    spellcasting: ClassSpellcasting | None = None


class SubclassRecord(Record):
    class_index: ContentSlug
    flavor: str
    desc: str


class LevelSpellcasting(Value):
    spell_slots: FrozenMap[int, int] = EMPTY_FROZEN_MAP
    cantrips_known: int | None = None
    spells_known: int | None = None


class ClassLevelRecord(Record):
    """Stores cumulative values; the ruleset computes per-level deltas."""

    kind: Literal["class"] = "class"
    level: int = Field(ge=1, le=20)
    class_index: ContentSlug
    prof_bonus: int = Field(ge=2)
    ability_score_bonuses: int = Field(ge=0)
    features: tuple[ContentSlug, ...] = ()
    spellcasting: LevelSpellcasting | None = None


class SubclassLevelRecord(Record):
    kind: Literal["subclass"] = "subclass"
    level: int = Field(ge=1, le=20)
    class_index: ContentSlug
    subclass_index: ContentSlug
    features: tuple[ContentSlug, ...] = ()


LevelRecord = Annotated[ClassLevelRecord | SubclassLevelRecord, Field(discriminator="kind")]


FeatureActivation = Literal["action", "bonus_action", "reaction", "special"]


class LevelResourceMaximum(Value):
    level: int = Field(ge=1, le=20)
    maximum: int = Field(ge=1)


class LevelScaledResourceMaximum(Value):
    kind: Literal["level_scaled"] = "level_scaled"
    levels: tuple[LevelResourceMaximum, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _in_level_order(self) -> Self:
        ordered = tuple(entry.level for entry in self.levels)
        if ordered != tuple(sorted(set(ordered))):
            raise ValueError("resource maximum levels must be unique and increasing")
        return self


class AbilityModifierResourceMaximum(Value):
    kind: Literal["ability_modifier"] = "ability_modifier"
    ability: Ability
    minimum: int = Field(default=1, ge=1)


class ClassLevelResourceMaximum(Value):
    kind: Literal["class_level"] = "class_level"
    multiplier: int = Field(default=1, ge=1)


DynamicResourceMaximum = Annotated[
    LevelScaledResourceMaximum | AbilityModifierResourceMaximum | ClassLevelResourceMaximum,
    Field(discriminator="kind"),
]
FeatureResourceMaximum = Annotated[int, Field(ge=1)] | DynamicResourceMaximum
FeatureResourceCost = Annotated[int, Field(ge=1)] | Literal["variable"]


class FeatureResource(Value):
    maximum: FeatureResourceMaximum
    recharge: RestType
    # Names the feature whose pool this one spends from, rather than owning a pool of its own.
    pool: ContentSlug | None = None
    cost: FeatureResourceCost = 1


class SelfHealWithClassLevel(Value):
    kind: Literal["self_heal_with_class_level"] = "self_heal_with_class_level"
    dice: PositiveDice


class RangedWeaponAttackBonus(Value):
    kind: Literal["ranged_weapon_attack_bonus"] = "ranged_weapon_attack_bonus"
    bonus: int


ActiveFeatureEffect = Annotated[SelfHealWithClassLevel, Field(discriminator="kind")]
PassiveFeatureEffect = Annotated[RangedWeaponAttackBonus, Field(discriminator="kind")]


class ProgressionOnlyFeatureMechanics(Value):
    kind: Literal["progression"] = "progression"


class AgentFeatureMechanics(Value):
    kind: Literal["agent"] = "agent"


class ResourceFeatureMechanics(Value):
    kind: Literal["resource"] = "resource"
    resource: FeatureResource


class AgentActiveFeatureMechanics(Value):
    kind: Literal["agent_active"] = "agent_active"
    activation: FeatureActivation
    resource: FeatureResource | None = None


class EngineActiveFeatureMechanics(Value):
    kind: Literal["engine_active"] = "engine_active"
    activation: FeatureActivation
    resource: FeatureResource | None = None
    effect: ActiveFeatureEffect


class EnginePassiveFeatureMechanics(Value):
    kind: Literal["engine_passive"] = "engine_passive"
    effect: PassiveFeatureEffect


FeatureMechanics = Annotated[
    ProgressionOnlyFeatureMechanics
    | AgentFeatureMechanics
    | ResourceFeatureMechanics
    | AgentActiveFeatureMechanics
    | EngineActiveFeatureMechanics
    | EnginePassiveFeatureMechanics,
    Field(discriminator="kind"),
]


class FeatureRecord(Record):
    class_index: ContentSlug
    level: int = Field(ge=1, le=20)
    desc: str
    subclass_index: ContentSlug | None = None
    parent: ContentSlug | None = None
    choices: tuple[ProgressionChoice, ...] = ()
    mechanics: FeatureMechanics
    replaces: tuple[ContentSlug, ...] = ()


class RaceRecord(Record):
    speed: int = Field(ge=0)
    size: CreatureSize
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    languages: tuple[LanguageName, ...] = ()
    traits: tuple[ContentSlug, ...] = ()
    subraces: tuple[ContentSlug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    alignment: str
    age: str
    size_description: str
    language_desc: str


class SubraceRecord(Record):
    race_index: ContentSlug
    desc: str
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    traits: tuple[ContentSlug, ...] = ()


class TraitRecord(Record):
    desc: str
    races: tuple[ContentSlug, ...] = ()
    subraces: tuple[ContentSlug, ...] = ()
    proficiencies: tuple[ContentSlug, ...] = ()
    parent: ContentSlug | None = None
    choices: tuple[ProgressionChoice, ...] = ()


class BackgroundRecord(Record):
    feature_name: str
    feature_desc: str
    starting_proficiencies: tuple[ContentSlug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    personality_traits: tuple[str, ...] = ()
    ideals: tuple[str, ...] = ()
    bonds: tuple[str, ...] = ()
    flaws: tuple[str, ...] = ()


class AbilityRequirement(Value):
    ability: Ability
    minimum_score: int = Field(ge=1)


class FeatRecord(Record):
    desc: str
    prerequisites: tuple[AbilityRequirement, ...] = ()


EquipmentProficiencyType = Literal[
    "Weapons", "Armor", "Artisan's Tools", "Musical Instruments", "Gaming Sets", "Vehicles", "Other"
]


class EquipmentProficiency(Record):
    """Stores expanded equipment indexes to avoid category lookups during play."""

    kind: Literal["equipment"] = "equipment"
    type: EquipmentProficiencyType
    equipment: tuple[ContentSlug, ...] = Field(min_length=1)


class SkillProficiency(Record):
    kind: Literal["skill"] = "skill"
    skill: ContentSlug


class SaveProficiency(Record):
    kind: Literal["save"] = "save"
    ability: Ability


ProficiencyRecord = Annotated[
    EquipmentProficiency | SkillProficiency | SaveProficiency, Field(discriminator="kind")
]
