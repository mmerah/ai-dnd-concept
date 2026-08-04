from collections import Counter

import pytest
from core_test_support import updated
from fivee_test_support import all_of, pack
from pydantic import ValidationError

from aidm.core.packs import ContentMiss, ContentRef, Record, loaded
from aidm.engines.dnd5e.content.pack_ruleset import compile_ruleset
from aidm.engines.dnd5e.content.records.character import (
    AbilityModifierResourceMaximum,
    AgentActiveFeatureMechanics,
    ClassLevelRecord,
    ClassLevelResourceMaximum,
    EngineActiveFeatureMechanics,
    EnginePassiveFeatureMechanics,
    FeatureRecord,
    LevelScaledResourceMaximum,
    RangedWeaponAttackBonus,
    ResourceFeatureMechanics,
    SelfHealWithClassLevel,
    SubclassLevelRecord,
)

PACK = pack()
FEATURES = all_of(PACK, "features", FeatureRecord)
LEVELS = all_of(PACK, "levels", Record)


def ref(collection: str, index: str) -> ContentRef:
    return ContentRef.model_validate({"pack": "srd-2014", "collection": collection, "index": index})


def test_every_feature_declares_a_resolution_kind() -> None:
    assert Counter(feature.mechanics.kind for feature in FEATURES.values()) == {
        "progression": 132,
        "agent": 250,
        "agent_active": 19,
        "resource": 3,
        "engine_active": 1,
        "engine_passive": 2,
    }
    assert {
        feature.index for feature in FEATURES.values() if feature.mechanics.kind == "engine_active"
    } == {"second-wind"}
    assert {
        feature.index for feature in FEATURES.values() if feature.mechanics.kind == "engine_passive"
    } == {"fighter-fighting-style-archery", "ranger-fighting-style-archery"}
    assert {
        feature.index for feature in FEATURES.values() if feature.mechanics.kind == "agent_active"
    } == {
        "action-surge-1-use",
        "action-surge-2-uses",
        "bardic-inspiration-d6",
        "bardic-inspiration-d8",
        "bardic-inspiration-d10",
        "bardic-inspiration-d12",
        "channel-divinity-preserve-life",
        "channel-divinity-sacred-weapon",
        "channel-divinity-turn-the-unholy",
        "channel-divinity-turn-undead",
        "flurry-of-blows",
        "lay-on-hands",
        "patient-defense",
        "rage",
        "step-of-the-wind",
        "stunning-strike",
        "wild-shape-cr-1-4-or-below-no-flying-or-swim-speed",
        "wild-shape-cr-1-2-or-below-no-flying-speed",
        "wild-shape-cr-1-or-below",
    }
    assert {
        feature.index for feature in FEATURES.values() if feature.mechanics.kind == "resource"
    } == {"channel-divinity", "channel-divinity-1-rest", "ki"}


def test_engine_resolved_features_carry_typed_effects() -> None:
    second_wind = FEATURES["second-wind"].mechanics
    assert isinstance(second_wind, EngineActiveFeatureMechanics)
    assert second_wind.activation == "bonus_action"
    assert second_wind.resource is not None
    assert (second_wind.resource.maximum, second_wind.resource.recharge) == (1, "short")
    assert isinstance(second_wind.effect, SelfHealWithClassLevel)
    assert second_wind.effect.dice == "1d10"
    for invalid in ("0", "MOD", "1d10 - 999"):
        with pytest.raises(ValidationError):
            updated(second_wind.effect, dice=invalid)

    for index in ("fighter-fighting-style-archery", "ranger-fighting-style-archery"):
        archery = FEATURES[index].mechanics
        assert isinstance(archery, EnginePassiveFeatureMechanics)
        assert isinstance(archery.effect, RangedWeaponAttackBonus)
        assert archery.effect.bonus == 2

    for index, maximum in (("action-surge-1-use", 1), ("action-surge-2-uses", 2)):
        action_surge = FEATURES[index].mechanics
        assert isinstance(action_surge, AgentActiveFeatureMechanics)
        assert action_surge.activation == "special"
        assert action_surge.resource is not None
        assert (action_surge.resource.maximum, action_surge.resource.recharge) == (
            maximum,
            "short",
        )


def test_feature_resources_carry_scaling_pools_costs_and_replacements() -> None:
    rage = FEATURES["rage"].mechanics
    assert isinstance(rage, AgentActiveFeatureMechanics)
    assert rage.resource is not None
    assert isinstance(rage.resource.maximum, LevelScaledResourceMaximum)
    assert [(entry.level, entry.maximum) for entry in rage.resource.maximum.levels] == [
        (1, 2),
        (3, 3),
        (6, 4),
        (12, 5),
        (17, 6),
    ]

    inspiration = FEATURES["bardic-inspiration-d6"].mechanics
    assert isinstance(inspiration, AgentActiveFeatureMechanics)
    assert inspiration.resource is not None
    assert isinstance(inspiration.resource.maximum, AbilityModifierResourceMaximum)

    ki = FEATURES["ki"].mechanics
    assert isinstance(ki, ResourceFeatureMechanics)
    assert isinstance(ki.resource.maximum, ClassLevelResourceMaximum)
    flurry = FEATURES["flurry-of-blows"].mechanics
    assert isinstance(flurry, AgentActiveFeatureMechanics)
    assert flurry.resource is not None and flurry.resource.pool == "ki"

    lay_on_hands = FEATURES["lay-on-hands"].mechanics
    assert isinstance(lay_on_hands, AgentActiveFeatureMechanics)
    assert lay_on_hands.resource is not None
    assert isinstance(lay_on_hands.resource.maximum, ClassLevelResourceMaximum)
    assert (lay_on_hands.resource.maximum.multiplier, lay_on_hands.resource.cost) == (
        5,
        "variable",
    )
    assert {
        feature.index: feature.replaces for feature in FEATURES.values() if feature.replaces
    } == {
        "action-surge-2-uses": ("action-surge-1-use",),
        "bardic-inspiration-d8": ("bardic-inspiration-d6",),
        "bardic-inspiration-d10": ("bardic-inspiration-d8",),
        "bardic-inspiration-d12": ("bardic-inspiration-d10",),
        "wild-shape-cr-1-2-or-below-no-flying-speed": (
            "wild-shape-cr-1-4-or-below-no-flying-or-swim-speed",
        ),
        "wild-shape-cr-1-or-below": ("wild-shape-cr-1-2-or-below-no-flying-speed",),
    }


def test_feature_mechanics_compile_from_pack_data_without_known_feature_ids() -> None:
    index = "fighter-fighting-style-defense"
    feature = updated(
        FEATURES[index],
        mechanics=EnginePassiveFeatureMechanics(effect=RangedWeaponAttackBonus(bonus=7)),
    )
    records = {**PACK.records, "features": {**FEATURES, index: feature}}
    compiled = compile_ruleset(loaded([updated(PACK, records=records)]))
    profile = compiled.feature(ref("features", index))
    assert not isinstance(profile, ContentMiss)
    assert isinstance(profile.mechanics, EnginePassiveFeatureMechanics)
    assert profile.mechanics.effect.bonus == 7


def test_a_shared_feature_resource_must_name_a_matching_pool_owner() -> None:
    flurry = FEATURES["flurry-of-blows"]
    mechanics = flurry.mechanics
    assert isinstance(mechanics, AgentActiveFeatureMechanics)
    assert mechanics.resource is not None
    changed = updated(
        flurry,
        mechanics=updated(
            mechanics,
            resource=updated(mechanics.resource, pool="patient-defense"),
        ),
    )
    records = {**PACK.records, "features": {**FEATURES, flurry.index: changed}}
    with pytest.raises(ValueError, match="patient-defense is not a resource feature"):
        compile_ruleset(loaded([updated(PACK, records=records)]))


def test_one_class_cannot_offer_a_choice_id_twice() -> None:
    first, second = FEATURES["rogue-expertise-1"], FEATURES["rogue-expertise-2"]
    clashing = updated(second, choices=(updated(second.choices[0], id=first.choices[0].id),))
    records = {**PACK.records, "features": {**FEATURES, second.index: clashing}}
    with pytest.raises(ValueError, match="rogue: choice ids offered more than once"):
        compile_ruleset(loaded([updated(PACK, records=records)]))


def test_a_feature_choice_cannot_grant_another_class_feature() -> None:
    container = FEATURES["additional-fighting-style"]
    (choice,) = container.choices
    rage = ref("features", "rage")
    changed_choice = updated(
        choice,
        options=(updated(choice.options[0], ref=rage), *choice.options[1:]),
    )
    changed = updated(container, choices=(changed_choice,))
    records = {**PACK.records, "features": {**FEATURES, container.index: changed}}
    with pytest.raises(ValueError, match="choice grants rage from class barbarian"):
        compile_ruleset(loaded([updated(PACK, records=records)]))


@pytest.mark.parametrize(
    ("level_index", "feature_index", "message"),
    [
        ("champion-3", "missing-champion-feature", "missing content"),
        ("fighter-2", "rage", "belongs to class 'barbarian', not 'fighter'"),
    ],
)
def test_every_class_and_subclass_feature_grant_is_validated(
    level_index: str,
    feature_index: str,
    message: str,
) -> None:
    level = LEVELS[level_index]
    assert isinstance(level, ClassLevelRecord | SubclassLevelRecord)
    changed = updated(level, features=(*level.features, feature_index))
    levels = {**LEVELS, level_index: changed}
    changed_pack = updated(PACK, records={**PACK.records, "levels": levels})
    with pytest.raises(ValueError, match=message):
        compile_ruleset(loaded([changed_pack]))
