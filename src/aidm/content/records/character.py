from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...utils.models import EMPTY_FROZEN_MAP, Ability, Frozen, FrozenMap
from ..vocabulary import LanguageName
from .base import ContentRef, CreatureSize, Record, Slug


class AbilityBonus(Frozen):
    ability: Ability
    bonus: int = Field(ge=1)

    def __str__(self) -> str:
        return f"+{self.bonus} {self.ability}"


class RecordOption(Frozen):
    kind: Literal["record"] = "record"
    label: str
    ref: ContentRef

    @property
    def key(self) -> str:
        return self.ref.index


class BonusOption(Frozen):
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


class ProgressionChoice(Frozen):
    """IDs stay stable because persisted decisions are keyed by them."""

    id: Slug
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
        return self

    def option(self, key: str) -> ChoiceOption | None:
        return next((o for o in self.options if o.key == key), None)


class SubclassChoice(Frozen):
    """Lives on the class because its feature provides only prose."""

    level: int = Field(ge=1, le=20)
    options: tuple[Slug, ...] = Field(min_length=1)


class ClassRecord(Record):
    hit_die: int = Field(ge=1)
    saving_throws: tuple[Ability, ...]
    proficiencies: tuple[Slug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    subclass: SubclassChoice | None = None
    spellcasting_ability: Ability | None = None


class SubclassRecord(Record):
    class_index: Slug
    flavor: str
    desc: str


class LevelSpellcasting(Frozen):
    spell_slots: FrozenMap[int, int] = EMPTY_FROZEN_MAP
    cantrips_known: int | None = None
    spells_known: int | None = None


class ClassLevelRecord(Record):
    """Stores cumulative values; the ruleset computes per-level deltas."""

    kind: Literal["class"] = "class"
    level: int = Field(ge=1, le=20)
    class_index: Slug
    prof_bonus: int = Field(ge=2)
    ability_score_bonuses: int = Field(ge=0)
    features: tuple[Slug, ...] = ()
    spellcasting: LevelSpellcasting | None = None


class SubclassLevelRecord(Record):
    kind: Literal["subclass"] = "subclass"
    level: int = Field(ge=1, le=20)
    class_index: Slug
    subclass_index: Slug
    features: tuple[Slug, ...] = ()


LevelRecord = Annotated[ClassLevelRecord | SubclassLevelRecord, Field(discriminator="kind")]


class FeatureRecord(Record):
    class_index: Slug
    level: int = Field(ge=1, le=20)
    desc: str
    subclass_index: Slug | None = None
    parent: Slug | None = None
    choices: tuple[ProgressionChoice, ...] = ()


class RaceRecord(Record):
    speed: int = Field(ge=0)
    size: CreatureSize
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    languages: tuple[LanguageName, ...] = ()
    traits: tuple[Slug, ...] = ()
    subraces: tuple[Slug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    alignment: str
    age: str
    size_description: str
    language_desc: str


class SubraceRecord(Record):
    race_index: Slug
    desc: str
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    traits: tuple[Slug, ...] = ()


class TraitRecord(Record):
    desc: str
    races: tuple[Slug, ...] = ()
    subraces: tuple[Slug, ...] = ()
    proficiencies: tuple[Slug, ...] = ()
    parent: Slug | None = None
    choices: tuple[ProgressionChoice, ...] = ()


class BackgroundRecord(Record):
    feature_name: str
    feature_desc: str
    starting_proficiencies: tuple[Slug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    personality_traits: tuple[str, ...] = ()
    ideals: tuple[str, ...] = ()
    bonds: tuple[str, ...] = ()
    flaws: tuple[str, ...] = ()


class AbilityRequirement(Frozen):
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
    equipment: tuple[Slug, ...] = Field(min_length=1)


class SkillProficiency(Record):
    kind: Literal["skill"] = "skill"
    skill: Slug


class SaveProficiency(Record):
    kind: Literal["save"] = "save"
    ability: Ability


ProficiencyRecord = Annotated[
    EquipmentProficiency | SkillProficiency | SaveProficiency, Field(discriminator="kind")
]
