"""Progression: what a class, a race and a background make of a character.

Upstream ships every decision as a recursive `Choice`/`OptionSet` tree. It is flattened here — at
the pack boundary, once — into a non-recursive `ProgressionChoice`, so `domain/` and `engine/` never
walk a tree. Starting equipment is deliberately absent: it is inventory rather than progression,
`CharacterSheet.starting_items` already owns what a game begins with, and it is the only part of
the tree that does not flatten exactly (see `scripts/srd/character.py`)."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...utils.models import Ability, Frozen, FrozenMap
from ..vocabulary import LanguageName
from .base import ContentRef, CreatureSize, Record, Slug


class AbilityBonus(Frozen):
    ability: Ability
    bonus: int = Field(ge=1)

    def __str__(self) -> str:
        return f"+{self.bonus} {self.ability}"


# Each arm carries its own `key` rather than storing one, so a saved decision can never name an
# option key the option itself disagrees with.
class RecordOption(Frozen):
    """A pick granting a record: a proficiency, a language, a spell, a trait, a subfeature. The ref
    is a full triple because a single choice's options are the one place the collection varies."""

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

# What taking an option does. Expertise doubles a proficiency the character already holds rather
# than granting one, and the two are indistinguishable from the option list alone — every skill is
# offered either way — so the choice has to say which it is.
ChoiceEffect = Literal["grant", "double"]


class ProgressionChoice(Frozen):
    """One decision the player makes: `choose` picks from `options`.

    `id` is unique pack-wide, because it is what a saved character's decisions are keyed by — an id
    that moved would silently re-point a choice already made."""

    id: Slug
    prompt: str
    choose: int = Field(ge=1)
    # An ability score improvement is the one choice a pick may repeat (+2 to one score is +1
    # twice); everything else is a set.
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
    """The only machine-readable option set upstream ships: the `martial-archetype` feature carries
    no option list at all, only an English sentence, so a subclass is chosen off the class."""

    level: int = Field(ge=1, le=20)
    options: tuple[Slug, ...] = Field(min_length=1)


class ClassRecord(Record):
    hit_die: int = Field(ge=1)
    saving_throws: tuple[Ability, ...]
    # Proficiency indexes granted outright; `choices` are the ones the player makes instead.
    proficiencies: tuple[Slug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    subclass: SubclassChoice | None = None
    spellcasting_ability: Ability | None = None  # absent on the four classes that cast nothing


class SubclassRecord(Record):
    class_index: Slug
    flavor: str  # 'Martial Archetype' — what the class calls its subclasses
    desc: str


class LevelSpellcasting(Frozen):
    """Only non-zero slot counts are kept: upstream writes levels 6-9 as an explicit 0 on 120 level
    records and omits them on 40, and both mean the same thing."""

    spell_slots: FrozenMap[int, int] = Field(default_factory=dict, validate_default=True)
    cantrips_known: int | None = None
    spells_known: int | None = None


class ClassLevelRecord(Record):
    """A cumulative snapshot, never a delta: `ability_score_bonuses` runs 0, 0, 0, 1, 1, 2 over
    Fighter 1-6, so a level-up is the *diff* of two records. Applying one whole double-counts."""

    kind: Literal["class"] = "class"
    level: int = Field(ge=1, le=20)
    class_index: Slug
    prof_bonus: int = Field(ge=2)
    ability_score_bonuses: int = Field(ge=0)
    features: tuple[Slug, ...] = ()
    spellcasting: LevelSpellcasting | None = None


class SubclassLevelRecord(Record):
    """What a subclass adds at a level, which is features and nothing else — discriminated from the
    class record rather than sharing it, so a missing `prof_bonus` cannot be read as 0."""

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
    parent: Slug | None = None  # 84 of 407 are a subfeature of another feature
    choices: tuple[ProgressionChoice, ...] = ()


class RaceRecord(Record):
    speed: int = Field(ge=0)
    size: CreatureSize
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    languages: tuple[LanguageName, ...] = ()
    traits: tuple[Slug, ...] = ()
    subraces: tuple[Slug, ...] = ()
    choices: tuple[ProgressionChoice, ...] = ()
    # Prose a role may use and no rule reads: the typed/opaque line, on the descriptive side.
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
    # Narrative prompts, not mechanics: nothing rolls against an ideal.
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
    """`equipment` holds the indexes this makes you proficient with, an upstream
    `equipment_category` reference expanded to its members at import — so a to-hit asks whether the
    weapon is in the set and never re-derives a category mid-turn."""

    kind: Literal["equipment"] = "equipment"
    type: EquipmentProficiencyType
    equipment: tuple[Slug, ...] = Field(min_length=1)


class SkillProficiency(Record):
    kind: Literal["skill"] = "skill"
    skill: Slug


class SaveProficiency(Record):
    kind: Literal["save"] = "save"
    ability: Ability


# Discriminated because the three answer different questions: what you may wield, what you add a
# bonus to, and which save you are good at.
ProficiencyRecord = Annotated[
    EquipmentProficiency | SkillProficiency | SaveProficiency, Field(discriminator="kind")
]
