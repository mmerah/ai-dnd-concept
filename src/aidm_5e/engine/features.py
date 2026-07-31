from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..content.library import ContentMiss
from ..content.records.base import ContentRef
from ..content.records.character import (
    AbilityModifierResourceMaximum,
    AgentActiveFeatureMechanics,
    ClassLevelResourceMaximum,
    EngineActiveFeatureMechanics,
    EnginePassiveFeatureMechanics,
    FeatureResource,
    FeatureResourceCost,
    LevelScaledResourceMaximum,
    RangedWeaponAttackBonus,
    ResourceFeatureMechanics,
    SelfHealWithClassLevel,
)
from ..content.vocabulary import RestType
from ..domain.models.consequences import UseFeature
from ..domain.models.facts import (
    Emitted,
    FeatureActivated,
    FeatureUsed,
    PoolRefilled,
)
from ..domain.models.progression import (
    FeatureKey,
    Progression,
    ResourceState,
    feature_key,
)
from ..utils.models import Attributes
from . import rules
from .mechanics import health
from .mechanics.resolution import Resolution
from .ruleset import FeatureProfile, FeatureRules, WeaponProfile


@dataclass(frozen=True, slots=True)
class FeaturePool:
    """The use counter a feature spends from, which several features may share."""

    ref: ContentRef
    cost: FeatureResourceCost
    state: ResourceState


@dataclass(frozen=True, slots=True)
class OwnedFeature:
    profile: FeatureProfile
    pool: FeaturePool | None = None


def profile_of(ref: ContentRef, ruleset: FeatureRules) -> FeatureProfile:
    found = ruleset.feature(ref)
    if isinstance(found, ContentMiss):
        raise ValueError(found.summary)
    return found


def pool_of(profile: FeatureProfile) -> FeatureResource | None:
    mechanics = profile.mechanics
    if isinstance(
        mechanics,
        ResourceFeatureMechanics | AgentActiveFeatureMechanics | EngineActiveFeatureMechanics,
    ):
        return mechanics.resource
    return None


def capacity(resource: FeatureResource, class_level: int, attributes: Attributes) -> int:
    maximum = resource.maximum
    match maximum:
        case int():
            return maximum
        case LevelScaledResourceMaximum(levels=levels):
            reached = [entry.maximum for entry in levels if entry.level <= class_level]
            if not reached:
                raise ValueError(f"resource has no maximum at class level {class_level}")
            return reached[-1]
        case AbilityModifierResourceMaximum(ability=ability, minimum=minimum):
            return max(minimum, rules.modifier(attributes, ability))
        case ClassLevelResourceMaximum(multiplier=multiplier):
            return class_level * multiplier


def owned(
    progression: Progression,
    attributes: Attributes,
    ruleset: FeatureRules,
) -> tuple[OwnedFeature, ...]:
    statuses: list[OwnedFeature] = []
    referenced: set[FeatureKey] = set()
    for ref in progression.features:
        profile = profile_of(ref, ruleset)
        resource = pool_of(profile)
        if resource is None:
            statuses.append(OwnedFeature(profile=profile))
            continue
        pool_ref = _pool_ref(profile, resource)
        key = feature_key(pool_ref)
        referenced.add(key)
        state = progression.feature_resources.get(key)
        if state is None:
            raise ValueError(f"limited feature {ref.index!r} has no {pool_ref.index!r} use counter")
        if (state.maximum, state.recharge) != (
            capacity(resource, progression.level, attributes),
            resource.recharge,
        ):
            raise ValueError(f"feature {ref.index!r} resource state does not match its profile")
        statuses.append(
            OwnedFeature(
                profile=profile,
                pool=FeaturePool(ref=pool_ref, cost=resource.cost, state=state),
            )
        )
    if unknown := sorted(set(progression.feature_resources) - referenced):
        raise ValueError(f"feature resource counters are not referenced: {unknown}")
    return tuple(statuses)


def acquire(
    held: Sequence[ContentRef],
    resources: Mapping[FeatureKey, ResourceState],
    grants: Sequence[FeatureProfile],
    *,
    ruleset: FeatureRules,
    class_level: int,
    attributes: Attributes,
) -> tuple[tuple[ContentRef, ...], dict[FeatureKey, ResourceState]]:
    features = list(held)
    inherited_spent: dict[FeatureKey, int] = {}
    replaced_keys: set[FeatureKey] = set()
    for grant in grants:
        replaced = set(grant.replaces)
        if missing := sorted(str(ref) for ref in replaced - set(features)):
            raise ValueError(f"feature {grant.ref.index!r} replaces features not held: {missing}")
        keys = _pool_keys(replaced, ruleset)
        replaced_keys |= keys
        spends = [state.spent for key in keys if (state := resources.get(key)) is not None]
        if len(spends) > 1:
            raise ValueError(f"feature {grant.ref.index!r} replaces multiple resource pools")
        if spends and (resource := pool_of(grant)) is not None:
            inherited_spent[feature_key(_pool_ref(grant, resource))] = spends[0]
        features = [ref for ref in features if ref not in replaced]
        if grant.ref in features:
            raise ValueError(f"feature {grant.ref.index!r} is already held")
        features.append(grant.ref)
    pools = _pools(features, ruleset, class_level, attributes)
    if unknown := sorted(set(resources) - set(pools) - replaced_keys):
        raise ValueError(f"feature resource counters are not referenced: {unknown}")
    states = {
        key: ResourceState(
            remaining=max(0, maximum - _spent(resources.get(key), inherited_spent.get(key, 0))),
            maximum=maximum,
            recharge=recharge,
        )
        for key, (recharge, maximum) in pools.items()
    }
    return tuple(features), states


def use(ctx: Resolution, consequence: UseFeature) -> list[Emitted]:
    progression = ctx.progression
    status = _named(
        owned(progression, ctx.player.stats.attributes, ctx.ruleset), consequence.feature
    )
    mechanics = status.profile.mechanics
    if not isinstance(mechanics, AgentActiveFeatureMechanics | EngineActiveFeatureMechanics):
        raise ValueError(f"feature {consequence.feature!r} is not directly invokable")
    spent = _spend(status, consequence.amount)
    match mechanics:
        case AgentActiveFeatureMechanics():
            return [*spent, FeatureActivated(ref=status.profile.ref, name=status.profile.name)]
        case EngineActiveFeatureMechanics(effect=SelfHealWithClassLevel(dice=healing_dice)):
            amount = f"{healing_dice} + {progression.level}"
            return [*spent, *health.hp_facts(ctx, None, amount, sign=1)]


def recharged(ctx: Resolution, completed: RestType) -> tuple[PoolRefilled, ...]:
    """Several features may share one counter, so refill each counter once."""
    refilled = {
        status.pool.ref: status.pool.state
        for status in owned(ctx.progression, ctx.player.stats.attributes, ctx.ruleset)
        if status.pool is not None and status.pool.state.refills(completed)
    }
    for state in refilled.values():
        state.remaining = state.maximum
    return tuple(
        # Named after the feature that owns the counter, not whoever spends from it.
        PoolRefilled(ref=ref, name=profile_of(ref, ctx.ruleset).name, maximum=state.maximum)
        for ref, state in refilled.items()
    )


def ranged_attack_bonus(
    progression: Progression | None,
    attributes: Attributes,
    weapon: WeaponProfile,
    ruleset: FeatureRules,
) -> int:
    if progression is None or not weapon.ranged:
        return 0
    return sum(_ranged_bonus(status.profile) for status in owned(progression, attributes, ruleset))


def _ranged_bonus(profile: FeatureProfile) -> int:
    """Match the effect, so a passive effect the engine gains later is not read as this one."""
    match profile.mechanics:
        case EnginePassiveFeatureMechanics(effect=RangedWeaponAttackBonus(bonus=bonus)):
            return bonus
        case _:
            return 0


def directly_invokable(profile: FeatureProfile) -> bool:
    return isinstance(profile.mechanics, AgentActiveFeatureMechanics | EngineActiveFeatureMechanics)


def actionability(profile: FeatureProfile) -> str:
    match profile.mechanics:
        case AgentActiveFeatureMechanics(activation=activation):
            return f"description-guided {activation}"
        case EngineActiveFeatureMechanics(activation=activation):
            return f"engine-resolved {activation}"
        case EnginePassiveFeatureMechanics():
            return "engine-resolved passive"
        case ResourceFeatureMechanics():
            return "resource-tracked"
        case _:
            return "description-guided"


def _pool_keys(features: set[ContentRef], ruleset: FeatureRules) -> set[FeatureKey]:
    keys: set[FeatureKey] = set()
    for profile in (profile_of(ref, ruleset) for ref in features):
        if (resource := pool_of(profile)) is not None:
            keys.add(feature_key(_pool_ref(profile, resource)))
    return keys


def _pools(
    features: Sequence[ContentRef],
    ruleset: FeatureRules,
    class_level: int,
    attributes: Attributes,
) -> dict[FeatureKey, tuple[RestType, int]]:
    pools: dict[FeatureKey, tuple[RestType, int]] = {}
    for profile in (profile_of(ref, ruleset) for ref in features):
        resource = pool_of(profile)
        if resource is None:
            continue
        pool_ref = _pool_ref(profile, resource)
        if pool_ref not in features:
            raise ValueError(
                f"feature {profile.ref.index!r} uses unheld resource pool {pool_ref.index!r}"
            )
        agreed = (resource.recharge, capacity(resource, class_level, attributes))
        if pools.setdefault(feature_key(pool_ref), agreed) != agreed:
            raise ValueError(f"resource pool {pool_ref.index!r} has conflicting rules")
    return pools


def _spent(before: ResourceState | None, inherited: int) -> int:
    return inherited if before is None else before.spent


def _spend(status: OwnedFeature, amount: int) -> list[Emitted]:
    pool = status.pool
    if pool is None:
        if amount != 1:
            raise ValueError(f"unlimited feature {status.profile.ref.index!r} takes no amount")
        return []
    state = pool.state
    if pool.cost != "variable" and amount != pool.cost:
        raise ValueError(f"feature {status.profile.ref.index!r} costs {pool.cost} use")
    if state.remaining < amount:
        raise ValueError(
            f"feature {status.profile.ref.index!r} has {state.remaining} uses left; "
            f"finish a {state.recharge} or longer rest"
        )
    state.remaining -= amount
    return [
        FeatureUsed(
            ref=pool.ref,
            name=status.profile.name,
            spent=amount,
            remaining=state.remaining,
            maximum=state.maximum,
        )
    ]


def _named(statuses: Sequence[OwnedFeature], key: FeatureKey) -> OwnedFeature:
    found = next((status for status in statuses if feature_key(status.profile.ref) == key), None)
    if found is None:
        raise ValueError(f"the player does not hold feature {key!r}")
    return found


def _pool_ref(profile: FeatureProfile, resource: FeatureResource) -> ContentRef:
    pool = resource.pool
    return profile.ref if pool is None else profile.ref.sibling("features", pool)
