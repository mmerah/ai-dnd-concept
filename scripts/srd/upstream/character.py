"""Classes, subclasses, levels, features, races, subraces, traits, backgrounds, feats and the
character half of proficiencies — everything reached through the recursive `Choice` tree."""

from pydantic import Field

from aidm_5e.content.records.base import CreatureSize
from aidm_5e.content.vocabulary import LanguageName

from .base import ApiRef, NamedRef, Upstream


# --- progression -------------------------------------------------------------------------------
# One `Option`/`OptionSet`/`Choice` triple covers all 119 non-monster choice nodes. It is one
# permissive model rather than a union per `option_type` because `scripts/srd/choices.py` is the
# boundary that narrows it: an option shape this pack does not project must raise there, naming the
# offending value, and a union here would instead fail with a validation error listing 11 arms.
class Option(Upstream):
    option_type: str
    item: NamedRef | None = None
    ability_score: ApiRef | None = None
    bonus: int | None = None
    items: list["Option"] = Field(default_factory=list)
    choice: "Choice | None" = None
    string: str | None = None
    desc: str | None = None


class ChoiceOptions(Upstream):
    option_set_type: str
    options: list[Option] = Field(default_factory=list)


class Choice(Upstream):
    choose: int
    desc: str | None = None
    options: ChoiceOptions = Field(alias="from")


Option.model_rebuild()


class Class(Upstream):
    index: str
    name: str
    hit_die: int
    saving_throws: list[ApiRef]
    proficiencies: list[ApiRef] = Field(default_factory=list)
    proficiency_choices: list[Choice] = Field(default_factory=list)
    subclasses: list[ApiRef] = Field(default_factory=list)
    spellcasting: "ClassSpellcasting | None" = None


class ClassSpellcasting(Upstream):
    spellcasting_ability: ApiRef


Class.model_rebuild()


class Subclass(Upstream):
    index: str
    name: str
    subclass_flavor: str
    desc: list[str]
    subclass_class: ApiRef = Field(alias="class")


class UpstreamLevelSpellcasting(Upstream):
    """Slot counts arrive as nine separate fields; `model_extra` is not used because `extra` is
    `ignore`, so each is named."""

    cantrips_known: int | None = None
    spells_known: int | None = None
    spell_slots_level_1: int = 0
    spell_slots_level_2: int = 0
    spell_slots_level_3: int = 0
    spell_slots_level_4: int = 0
    spell_slots_level_5: int = 0
    spell_slots_level_6: int = 0
    spell_slots_level_7: int = 0
    spell_slots_level_8: int = 0
    spell_slots_level_9: int = 0

    @property
    def slots(self) -> dict[int, int]:
        counts = (
            self.spell_slots_level_1,
            self.spell_slots_level_2,
            self.spell_slots_level_3,
            self.spell_slots_level_4,
            self.spell_slots_level_5,
            self.spell_slots_level_6,
            self.spell_slots_level_7,
            self.spell_slots_level_8,
            self.spell_slots_level_9,
        )
        return {level: count for level, count in enumerate(counts, 1) if count}


class Level(Upstream):
    index: str
    level: int
    level_class: ApiRef = Field(alias="class")
    subclass: ApiRef | None = None
    prof_bonus: int | None = None
    ability_score_bonuses: int | None = None
    features: list[ApiRef] = Field(default_factory=list)
    spellcasting: UpstreamLevelSpellcasting | None = None


class FeatureSpecific(Upstream):
    subfeature_options: Choice | None = None
    expertise_options: Choice | None = None


class Feature(Upstream):
    index: str
    name: str
    level: int
    desc: list[str]
    feature_class: ApiRef = Field(alias="class")
    subclass: ApiRef | None = None
    parent: ApiRef | None = None
    feature_specific: FeatureSpecific | None = None


class UpstreamAbilityBonus(Upstream):
    ability_score: ApiRef
    bonus: int


class LanguageRef(Upstream):
    index: LanguageName


class Race(Upstream):
    index: str
    name: str
    speed: int
    size: CreatureSize
    ability_bonuses: list[UpstreamAbilityBonus] = Field(default_factory=list)
    ability_bonus_options: Choice | None = None
    languages: list[LanguageRef] = Field(default_factory=list)
    language_options: Choice | None = None
    traits: list[ApiRef] = Field(default_factory=list)
    subraces: list[ApiRef] = Field(default_factory=list)
    alignment: str
    age: str
    size_description: str
    language_desc: str


class Subrace(Upstream):
    index: str
    name: str
    race: ApiRef
    desc: str
    ability_bonuses: list[UpstreamAbilityBonus] = Field(default_factory=list)
    racial_traits: list[ApiRef] = Field(default_factory=list)


class TraitSpecific(Upstream):
    spell_options: Choice | None = None
    subtrait_options: Choice | None = None


class Trait(Upstream):
    index: str
    name: str
    desc: list[str]
    races: list[ApiRef] = Field(default_factory=list)
    subraces: list[ApiRef] = Field(default_factory=list)
    proficiencies: list[ApiRef] = Field(default_factory=list)
    proficiency_choices: Choice | None = None
    language_options: Choice | None = None
    parent: ApiRef | None = None
    trait_specific: TraitSpecific | None = None


class BackgroundFeature(Upstream):
    name: str
    desc: list[str]


class Background(Upstream):
    index: str
    name: str
    starting_proficiencies: list[ApiRef] = Field(default_factory=list)
    language_options: Choice | None = None
    feature: BackgroundFeature
    personality_traits: Choice | None = None
    ideals: Choice | None = None
    bonds: Choice | None = None
    flaws: Choice | None = None


class ScorePrerequisite(Upstream):
    ability_score: ApiRef
    minimum_score: int


class Feat(Upstream):
    index: str
    name: str
    desc: list[str]
    prerequisites: list[ScorePrerequisite] = Field(default_factory=list)


class ProficiencyReference(Upstream):
    """The url is read as well as the index, because it is the only thing saying which collection a
    proficiency refers into: 85 name an Equipment, 8 an Equipment-Category, 18 a Skill, 6 an
    Ability-Score."""

    index: str
    url: str


class UpstreamProficiency(Upstream):
    """A record of the Proficiencies collection. `Proficiency` above is the differently shaped entry
    a *monster* carries — upstream uses the one word for both."""

    index: str
    name: str
    type: str
    reference: ProficiencyReference
