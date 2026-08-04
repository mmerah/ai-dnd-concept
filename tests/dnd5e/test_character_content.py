import pytest
from core_test_support import updated
from fivee_test_support import all_of, content, pack, ruleset

from aidm.core.packs import ContentRef, Record, loaded
from aidm.engines.dnd5e.content.pack_ruleset import compile_ruleset
from aidm.engines.dnd5e.content.records.character import (
    BackgroundRecord,
    ClassLevelRecord,
    ClassRecord,
    EquipmentProficiency,
    FeatureRecord,
    RaceRecord,
    RecordOption,
    SaveProficiency,
    SkillProficiency,
    SubclassLevelRecord,
    TraitRecord,
)
from aidm.engines.dnd5e.state import MAX_LEVEL, Origin

PACK = pack()
CONTENT = content()
RULES = ruleset()
CLASSES = all_of(PACK, "classes", ClassRecord)
FEATURES = all_of(PACK, "features", FeatureRecord)
LEVELS = all_of(PACK, "levels", Record)
PROFICIENCIES = all_of(PACK, "proficiencies", Record)
CHOICES = [
    choice
    for records in (
        CLASSES,
        FEATURES,
        all_of(PACK, "races", RaceRecord),
        all_of(PACK, "traits", TraitRecord),
        all_of(PACK, "backgrounds", BackgroundRecord),
    )
    for record in records.values()
    for choice in record.choices
]


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def test_a_level_record_is_a_class_one_or_a_subclass_one() -> None:
    levels = list(LEVELS.values())
    assert sum(isinstance(level, ClassLevelRecord) for level in levels) == 240
    assert sum(isinstance(level, SubclassLevelRecord) for level in levels) == 50
    fighter = [LEVELS[f"fighter-{level}"] for level in range(1, 7)]
    assert [
        level.ability_score_bonuses for level in fighter if isinstance(level, ClassLevelRecord)
    ] == [0, 0, 0, 1, 1, 2]


def test_every_class_grants_its_improvements_at_the_levels_5e_says() -> None:
    extra = {"fighter": {6, 14}, "rogue": {10}}
    for klass in CLASSES:
        improvement_levels = {4, 8, 12, 16, 19} | extra.get(klass, set())
        totals = [LEVELS[f"{klass}-{level}"] for level in range(1, MAX_LEVEL + 1)]
        assert [
            total.ability_score_bonuses for total in totals if isinstance(total, ClassLevelRecord)
        ] == [
            sum(1 for improvement in improvement_levels if improvement <= level)
            for level in range(1, MAX_LEVEL + 1)
        ]
    rogue = Origin(class_ref=ref("classes", "rogue"))
    assert [RULES.level(rogue, level).improvements for level in range(8, 14)] == [
        1,
        0,
        1,
        0,
        1,
        0,
    ]


def test_a_class_ladder_that_falls_is_refused_at_load_not_absorbed() -> None:
    fallen = updated(LEVELS["rogue-11"], ability_score_bonuses=2)
    records = {**PACK.records, "levels": {**LEVELS, "rogue-11": fallen}}
    with pytest.raises(
        ValueError,
        match="rogue-11: ability score improvements fall from 3 to 2",
    ):
        compile_ruleset(loaded([updated(PACK, records=records)]))


def test_every_class_can_be_played_and_ships_one_subclass() -> None:
    classes = list(CLASSES.values())
    assert len(classes) == 12
    assert all(
        record.subclass is not None and len(record.subclass.options) == 1 for record in classes
    )
    assert sum(1 for record in classes if record.spellcasting) == 8
    subclass = CLASSES["cleric"].subclass
    assert subclass is not None and subclass.level == 1


def test_a_choice_id_is_unique_pack_wide_and_every_option_resolves() -> None:
    ids = [choice.id for choice in CHOICES]
    assert len(ids) == len(set(ids)) == 41
    refs = [
        option.ref
        for choice in CHOICES
        for option in choice.options
        if isinstance(option, RecordOption)
    ]
    assert len(refs) == 387
    assert not [str(option_ref) for option_ref in refs if CONTENT.resolves(option_ref) is not None]


def test_only_an_expertise_choice_doubles_rather_than_grants() -> None:
    doubling = sorted(choice.id for choice in CHOICES if choice.effect == "double")
    assert doubling == [
        "bard-expertise-1-expertise",
        "bard-expertise-2-expertise",
        "rogue-expertise-1-expertise",
        "rogue-expertise-2-expertise",
    ]


def test_a_nested_choice_is_flattened_by_unioning_its_arms() -> None:
    tools = CLASSES["monk"].choices[1]
    assert (tools.choose, len(tools.options)) == (1, 29)
    (expertise,) = FEATURES["rogue-expertise-1"].choices
    assert (expertise.choose, len(expertise.options)) == (2, 19)


def test_a_proficiency_says_what_it_covers_rather_than_naming_a_category() -> None:
    kinds = [type(proficiency).__name__ for proficiency in PROFICIENCIES.values()]
    assert len(kinds) == 117
    assert kinds.count(EquipmentProficiency.__name__) == 93
    assert kinds.count(SkillProficiency.__name__) == 18
    assert kinds.count(SaveProficiency.__name__) == 6
    martial = PROFICIENCIES["martial-weapons"]
    assert isinstance(martial, EquipmentProficiency) and len(martial.equipment) == 23
