"""Classes, subclasses, levels, features, races, subraces, traits, backgrounds, feats and the
character half of proficiencies — everything reached through the tree `choices.py` flattens.

Starting equipment is deliberately not projected. It is inventory rather than progression,
`CharacterSheet.starting_items` already owns what a game begins with, and it is the only part of
the tree whose arms spend different numbers of picks — the one part `flatten` could not union."""

from collections.abc import Mapping, Sequence

from aidm.core.packs import ContentSlug
from aidm.engines.dnd5e.content.records.base import Collection
from aidm.engines.dnd5e.content.records.character import (
    AbilityBonus,
    AbilityRequirement,
    BackgroundRecord,
    ChoiceOption,
    ClassLevelRecord,
    ClassRecord,
    ClassSpellcasting,
    EquipmentProficiency,
    EquipmentProficiencyType,
    FeatRecord,
    FeatureRecord,
    LevelRecord,
    LevelSpellcasting,
    ProficiencyRecord,
    ProgressionChoice,
    RaceRecord,
    SaveProficiency,
    SkillProficiency,
    SubclassChoice,
    SubclassLevelRecord,
    SubclassRecord,
    SubraceRecord,
    TraitRecord,
)

from .choices import flatten
from .common import ability
from .feature_mechanics import mechanics_for, replacements_for
from .upstream.character import (
    Background,
    Choice,
    Class,
    Feat,
    Feature,
    Level,
    Race,
    Subclass,
    Subrace,
    Trait,
    UpstreamAbilityBonus,
    UpstreamProficiency,
)

# Upstream states each class's slot recharge only inside the "Spell Slots" prose, so the one class
# that regains slots on a short rest is named here rather than parsed out of a sentence.
_SHORT_REST_SLOTS: frozenset[ContentSlug] = frozenset({"warlock"})


def _bonuses(entries: Sequence[UpstreamAbilityBonus]) -> tuple[AbilityBonus, ...]:
    return tuple(
        AbilityBonus(ability=ability(e.ability_score.index), bonus=e.bonus) for e in entries
    )


def _prose(node: Choice | None) -> tuple[str, ...]:
    """A background's personality traits, ideals, bonds and flaws are `string`/`ideal` options —
    prompts a role may use and no rule reads, so they stay the prose they are rather than becoming
    decisions the engine would have to validate."""
    if node is None:
        return ()
    lines = [option.string or option.desc for option in node.options.options]
    if any(line is None for line in lines):
        raise ValueError(f"a narrative option carries no text: {node.options.options}")
    return tuple(line for line in lines if line is not None)


def klass(record: Class, subclass_levels: Mapping[str, int]) -> ClassRecord:
    """`subclass_levels` says at which level each subclass first grants something, which is when it
    is chosen: the feature announcing the choice (`martial-archetype`) carries no option list."""
    subclasses = tuple(s.index for s in record.subclasses)
    casting = record.spellcasting
    return ClassRecord(
        index=record.index,
        name=record.name,
        hit_die=record.hit_die,
        saving_throws=tuple(ability(s.index) for s in record.saving_throws),
        proficiencies=tuple(p.index for p in record.proficiencies),
        choices=tuple(
            flatten(node, f"{record.index}-proficiency-{n}", "proficiencies")
            for n, node in enumerate(record.proficiency_choices, 1)
        ),
        subclass=(
            None
            if not subclasses
            else SubclassChoice(
                level=min(subclass_levels[s] for s in subclasses), options=subclasses
            )
        ),
        spellcasting=(
            None
            if casting is None
            else ClassSpellcasting(
                ability=ability(casting.spellcasting_ability.index),
                slot_recharge="short" if record.index in _SHORT_REST_SLOTS else "long",
            )
        ),
    )


def subclass(record: Subclass) -> SubclassRecord:
    return SubclassRecord(
        index=record.index,
        name=record.name,
        class_index=record.subclass_class.index,
        flavor=record.subclass_flavor,
        desc="\n\n".join(record.desc),
    )


def level(record: Level) -> LevelRecord:
    features = tuple(f.index for f in record.features)
    if record.subclass is not None:
        return SubclassLevelRecord(
            index=record.index,
            name=record.index,  # upstream gives a level record no name of its own
            level=record.level,
            class_index=record.level_class.index,
            subclass_index=record.subclass.index,
            features=features,
        )
    if record.prof_bonus is None or record.ability_score_bonuses is None:
        raise ValueError(f"class level {record.index!r} is missing a cumulative total")
    casting = record.spellcasting
    return ClassLevelRecord(
        index=record.index,
        name=record.index,
        level=record.level,
        class_index=record.level_class.index,
        prof_bonus=record.prof_bonus,
        ability_score_bonuses=record.ability_score_bonuses,
        features=features,
        spellcasting=(
            None
            if casting is None
            else LevelSpellcasting(
                spell_slots=casting.slots,
                cantrips_known=casting.cantrips_known,
                spells_known=casting.spells_known,
            )
        ),
    )


def feature(record: Feature) -> FeatureRecord:
    """`subfeature_options` picks another feature (a fighting style, a metamagic) and
    `expertise_options` doubles a proficiency — real option lists, unlike the subclass choice."""
    specific = record.feature_specific
    choices: list[ProgressionChoice] = []
    if specific is not None and specific.subfeature_options is not None:
        choices.append(
            flatten(specific.subfeature_options, f"{record.index}-subfeature", "features")
        )
    if specific is not None and specific.expertise_options is not None:
        choices.append(
            flatten(
                specific.expertise_options,
                f"{record.index}-expertise",
                "proficiencies",
                effect="double",
            )
        )
    return FeatureRecord(
        index=record.index,
        name=record.name,
        class_index=record.feature_class.index,
        level=record.level,
        desc="\n\n".join(record.desc),
        subclass_index=None if record.subclass is None else record.subclass.index,
        parent=None if record.parent is None else record.parent.index,
        choices=tuple(choices),
        mechanics=mechanics_for(record.index, has_choices=bool(choices)),
        replaces=replacements_for(record.index),
    )


def race(record: Race) -> RaceRecord:
    choices: list[ProgressionChoice] = []
    if record.ability_bonus_options is not None:
        choices.append(flatten(record.ability_bonus_options, f"{record.index}-ability-bonuses"))
    if record.language_options is not None:
        choices.append(flatten(record.language_options, f"{record.index}-languages", "languages"))
    return RaceRecord(
        index=record.index,
        name=record.name,
        speed=record.speed,
        size=record.size,
        ability_bonuses=_bonuses(record.ability_bonuses),
        languages=tuple(language.index for language in record.languages),
        traits=tuple(t.index for t in record.traits),
        subraces=tuple(s.index for s in record.subraces),
        choices=tuple(choices),
        alignment=record.alignment,
        age=record.age,
        size_description=record.size_description,
        language_desc=record.language_desc,
    )


def subrace(record: Subrace) -> SubraceRecord:
    return SubraceRecord(
        index=record.index,
        name=record.name,
        race_index=record.race.index,
        desc=record.desc,
        ability_bonuses=_bonuses(record.ability_bonuses),
        traits=tuple(t.index for t in record.racial_traits),
    )


def trait(record: Trait) -> TraitRecord:
    specific = record.trait_specific
    nodes: tuple[tuple[Choice | None, str, Collection], ...] = (
        (record.proficiency_choices, "proficiency", "proficiencies"),
        (record.language_options, "languages", "languages"),
        (None if specific is None else specific.spell_options, "spell", "spells"),
        (None if specific is None else specific.subtrait_options, "subtrait", "traits"),
    )
    return TraitRecord(
        index=record.index,
        name=record.name,
        desc="\n\n".join(record.desc),
        races=tuple(r.index for r in record.races),
        subraces=tuple(s.index for s in record.subraces),
        proficiencies=tuple(p.index for p in record.proficiencies),
        parent=None if record.parent is None else record.parent.index,
        choices=tuple(
            flatten(node, f"{record.index}-{slot}", collection)
            for node, slot, collection in nodes
            if node is not None
        ),
    )


def background(record: Background, languages: Sequence[ChoiceOption]) -> BackgroundRecord:
    """`languages` is the whole Languages collection: the Acolyte's language choice is a
    `resource_list`, which names a collection by url instead of listing its members."""
    node = record.language_options
    return BackgroundRecord(
        index=record.index,
        name=record.name,
        feature_name=record.feature.name,
        feature_desc="\n\n".join(record.feature.desc),
        starting_proficiencies=tuple(p.index for p in record.starting_proficiencies),
        choices=(
            ()
            if node is None
            else (flatten(node, f"{record.index}-languages", "languages", universe=languages),)
        ),
        personality_traits=_prose(record.personality_traits),
        ideals=_prose(record.ideals),
        bonds=_prose(record.bonds),
        flaws=_prose(record.flaws),
    )


def feat(record: Feat) -> FeatRecord:
    return FeatRecord(
        index=record.index,
        name=record.name,
        desc="\n\n".join(record.desc),
        prerequisites=tuple(
            AbilityRequirement(
                ability=ability(p.ability_score.index), minimum_score=p.minimum_score
            )
            for p in record.prerequisites
        ),
    )


def proficiency(
    record: UpstreamProficiency, categories: Mapping[str, Sequence[str]]
) -> ProficiencyRecord:
    """An `equipment-categories` reference is expanded to its members here, so a to-hit asks whether
    the weapon is in the set rather than re-deriving a category mid-turn."""
    reference = record.reference
    match record.type, _collection_of(reference.url):
        case "Skills", "skills":
            return SkillProficiency(index=record.index, name=record.name, skill=reference.index)
        case "Saving Throws", "ability-scores":
            return SaveProficiency(
                index=record.index, name=record.name, ability=ability(reference.index)
            )
        case _, "equipment":
            equipment = (reference.index,)
        case _, "equipment-categories":
            equipment = tuple(categories[reference.index])
        case _, collection:
            raise ValueError(
                f"proficiency {record.index!r} of type {record.type!r} refers to {collection}"
            )
    return EquipmentProficiency(
        index=record.index,
        name=record.name,
        type=_equipment_type(record),
        equipment=equipment,
    )


def _collection_of(url: str) -> str:
    """`/api/2014/skills/perception` -> `skills`. The url is the only field naming the collection a
    reference points into, which is why a record's identity is a triple and not an index."""
    parts = url.split("/")
    if len(parts) != 5 or parts[:2] != ["", "api"]:
        raise ValueError(f"cannot read a collection out of {url!r}")
    return parts[3]


def _equipment_type(record: UpstreamProficiency) -> EquipmentProficiencyType:
    """Narrowed here rather than by typing the upstream field, because `type` also carries the two
    values that are not equipment at all."""
    match record.type:
        case (
            "Weapons"
            | "Armor"
            | "Artisan's Tools"
            | "Musical Instruments"
            | "Gaming Sets"
            | "Vehicles"
            | "Other"
        ):
            return record.type
        case _:
            raise ValueError(f"unknown proficiency type {record.type!r}")
