"""Curated mechanics for upstream features, which ship only prose.

A feature is classified here only when its rules are unambiguous enough for the engine to own them:
a use counter it can spend, or an effect type the engine already implements. Everything else stays
`agent`, where the Director applies the description through ordinary typed consequences — that is
the safe default, so an unlisted feature is never wrong, only unautomated.

Keyed by upstream index rather than parsed from the prose, because the prose states the numbers in
sentences and a parser would fail silently on the wording it did not anticipate."""

from aidm.plugins.dnd5e.content.records.character import (
    AbilityModifierResourceMaximum,
    AgentActiveFeatureMechanics,
    AgentFeatureMechanics,
    ClassLevelResourceMaximum,
    EngineActiveFeatureMechanics,
    EnginePassiveFeatureMechanics,
    FeatureActivation,
    FeatureMechanics,
    FeatureResource,
    FeatureResourceCost,
    FeatureResourceMaximum,
    LevelResourceMaximum,
    LevelScaledResourceMaximum,
    ProgressionOnlyFeatureMechanics,
    RangedWeaponAttackBonus,
    ResourceFeatureMechanics,
    SelfHealWithClassLevel,
)
from aidm.plugins.dnd5e.content.vocabulary import RestType
from aidm.plugins.dnd5e.values import ContentSlug

_CLASS_OR_SUBCLASS_SELECTIONS: frozenset[ContentSlug] = frozenset(
    {
        "arcane-tradition",
        "bard-college",
        "divine-domain",
        "druid-circle",
        "martial-archetype",
        "monastic-tradition",
        "otherworldly-patron",
        "primal-path",
        "ranger-archetype",
        "roguish-archetype",
        "sacred-oath",
        "sorcerous-origin",
    }
)

# Upstream ships one feature per Channel Divinity capacity. The level-scaled maximum below already
# covers every step, so the later two grant nothing and would otherwise duplicate the pool.
_RESOURCE_CAPACITY_ANNOUNCEMENTS: frozenset[ContentSlug] = frozenset(
    {
        "channel-divinity-2-rest",
        "channel-divinity-3-rest",
    }
)

_RAGE_MAXIMUM = LevelScaledResourceMaximum(
    levels=(
        LevelResourceMaximum(level=1, maximum=2),
        LevelResourceMaximum(level=3, maximum=3),
        LevelResourceMaximum(level=6, maximum=4),
        LevelResourceMaximum(level=12, maximum=5),
        LevelResourceMaximum(level=17, maximum=6),
    )
)
_CLERIC_CHANNEL_DIVINITY_MAXIMUM = LevelScaledResourceMaximum(
    levels=(
        LevelResourceMaximum(level=2, maximum=1),
        LevelResourceMaximum(level=6, maximum=2),
        LevelResourceMaximum(level=18, maximum=3),
    )
)
_BARDIC_INSPIRATION_MAXIMUM = AbilityModifierResourceMaximum(ability="charisma")
_KI_MAXIMUM = ClassLevelResourceMaximum()
_LAY_ON_HANDS_MAXIMUM = ClassLevelResourceMaximum(multiplier=5)


def mechanics_for(index: ContentSlug, *, has_choices: bool = False) -> FeatureMechanics:
    """Project curated mechanics; unclassified upstream prose stays description-guided."""
    match index:
        case "rage":
            return _active("bonus_action", maximum=_RAGE_MAXIMUM, recharge="long")
        case (
            "bardic-inspiration-d6"
            | "bardic-inspiration-d8"
            | "bardic-inspiration-d10"
            | "bardic-inspiration-d12"
        ):
            # Font of Inspiration moves the recharge to a short rest at level 5, the same level
            # that upgrades the die to a d8, so the die identifies the recharge.
            recharge = "long" if index == "bardic-inspiration-d6" else "short"
            return _active(
                "bonus_action",
                maximum=_BARDIC_INSPIRATION_MAXIMUM,
                recharge=recharge,
            )
        case "ki":
            return ResourceFeatureMechanics(
                resource=FeatureResource(maximum=_KI_MAXIMUM, recharge="short")
            )
        case "flurry-of-blows" | "patient-defense" | "step-of-the-wind":
            return _active("bonus_action", maximum=_KI_MAXIMUM, recharge="short", pool="ki")
        case "stunning-strike":
            return _active("special", maximum=_KI_MAXIMUM, recharge="short", pool="ki")
        case "channel-divinity-1-rest":
            return ResourceFeatureMechanics(
                resource=FeatureResource(
                    maximum=_CLERIC_CHANNEL_DIVINITY_MAXIMUM,
                    recharge="short",
                )
            )
        case "channel-divinity-turn-undead" | "channel-divinity-preserve-life":
            return _active(
                "action",
                maximum=_CLERIC_CHANNEL_DIVINITY_MAXIMUM,
                recharge="short",
                pool="channel-divinity-1-rest",
            )
        case "channel-divinity":
            return ResourceFeatureMechanics(resource=FeatureResource(maximum=1, recharge="short"))
        case "channel-divinity-sacred-weapon" | "channel-divinity-turn-the-unholy":
            return _active("action", maximum=1, recharge="short", pool="channel-divinity")
        case (
            "wild-shape-cr-1-4-or-below-no-flying-or-swim-speed"
            | "wild-shape-cr-1-2-or-below-no-flying-speed"
            | "wild-shape-cr-1-or-below"
        ):
            return _active("action", maximum=2, recharge="short")
        case "lay-on-hands":
            return _active(
                "action",
                maximum=_LAY_ON_HANDS_MAXIMUM,
                recharge="long",
                cost="variable",
            )
        case "second-wind":
            return EngineActiveFeatureMechanics(
                activation="bonus_action",
                resource=FeatureResource(maximum=1, recharge="short"),
                effect=SelfHealWithClassLevel(dice="1d10"),
            )
        case "fighter-fighting-style-archery" | "ranger-fighting-style-archery":
            return EnginePassiveFeatureMechanics(effect=RangedWeaponAttackBonus(bonus=2))
        case "action-surge-1-use":
            return AgentActiveFeatureMechanics(
                activation="special",
                resource=FeatureResource(maximum=1, recharge="short"),
            )
        case "action-surge-2-uses":
            return AgentActiveFeatureMechanics(
                activation="special",
                resource=FeatureResource(maximum=2, recharge="short"),
            )
        case _ if _is_progression_only(index, has_choices):
            return ProgressionOnlyFeatureMechanics()
        case _:
            return AgentFeatureMechanics()


def replacements_for(index: ContentSlug) -> tuple[ContentSlug, ...]:
    replacements: dict[ContentSlug, ContentSlug] = {
        "action-surge-2-uses": "action-surge-1-use",
        "bardic-inspiration-d8": "bardic-inspiration-d6",
        "bardic-inspiration-d10": "bardic-inspiration-d8",
        "bardic-inspiration-d12": "bardic-inspiration-d10",
        "wild-shape-cr-1-2-or-below-no-flying-speed": (
            "wild-shape-cr-1-4-or-below-no-flying-or-swim-speed"
        ),
        "wild-shape-cr-1-or-below": "wild-shape-cr-1-2-or-below-no-flying-speed",
    }
    replaced = replacements.get(index)
    return () if replaced is None else (replaced,)


def _active(
    activation: FeatureActivation,
    *,
    maximum: FeatureResourceMaximum,
    recharge: RestType,
    pool: ContentSlug | None = None,
    cost: FeatureResourceCost = 1,
) -> AgentActiveFeatureMechanics:
    return AgentActiveFeatureMechanics(
        activation=activation,
        resource=FeatureResource(
            maximum=maximum,
            recharge=recharge,
            pool=pool,
            cost=cost,
        ),
    )


def _is_progression_only(index: ContentSlug, has_choices: bool) -> bool:
    return (
        has_choices
        or "-ability-score-improvement-" in index
        or index in _CLASS_OR_SUBCLASS_SELECTIONS
        or any(
            index.startswith(f"{selection}-improvement-")
            for selection in _CLASS_OR_SUBCLASS_SELECTIONS
        )
        or index in _RESOURCE_CAPACITY_ANNOUNCEMENTS
    )
